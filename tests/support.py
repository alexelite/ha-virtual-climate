"""Load production logic with HA I/O doubles; validation uses real Voluptuous."""
import ast
import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import inspect
import importlib.util
import logging
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
_supply_spec = importlib.util.spec_from_file_location('virtual_climate_supply', ROOT / 'custom_components/virtual_climate/supply_control.py')
supply_module = importlib.util.module_from_spec(_supply_spec)
_supply_spec.loader.exec_module(supply_module)
_filter_spec = importlib.util.spec_from_file_location('virtual_climate_filter', ROOT / 'custom_components/virtual_climate/temperature_filter.py')
filter_module = importlib.util.module_from_spec(_filter_spec)
_filter_spec.loader.exec_module(filter_module)


class MemoryStore:
    def __init__(self, hass, version, key):
        self.storage = hass.__dict__.setdefault('storage', {})
        self.key = key

    @property
    def data(self):
        return self.storage.get(self.key)

    @data.setter
    def data(self, value):
        self.storage[self.key] = value

    async def async_load(self):
        return deepcopy(self.data)

    async def async_save(self, data):
        self.data = deepcopy(data)

    def async_delay_save(self, data_func, delay=0):
        self.data = deepcopy(data_func())


def callback(fn):
    fn._hass_callback = True
    return fn


def load_source(filename, namespace, skip_classes=()):
    path = ROOT / 'custom_components/virtual_climate' / filename
    tree = ast.parse(path.read_text())
    tree.body = [node for node in tree.body
                 if not isinstance(node, (ast.Import, ast.ImportFrom))
                 and not (isinstance(node, ast.ClassDef) and node.name in skip_classes)]
    tree.body.insert(0, ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0))
    ast.fix_missing_locations(tree)
    exec(compile(tree, str(path), 'exec'), namespace)
    return namespace


class Clock:
    def __init__(self):
        self.now = 10000.0
        self.sleepers = []

    def time(self):
        return self.now

    async def sleep(self, seconds):
        future = asyncio.get_running_loop().create_future()
        self.sleepers.append((self.now + seconds, future))
        await future

    def advance(self, seconds):
        self.now += seconds
        for deadline, future in self.sleepers:
            if deadline <= self.now and not future.done():
                future.set_result(None)


class States:
    def __init__(self, clock):
        self.clock = clock
        self.values = {}
        self.listeners = []

    def get(self, entity_id):
        return self.values.get(entity_id)

    def set(self, entity_id, state, changed_at=None):
        previous = self.get(entity_id)
        if previous and previous.state == state:
            return
        timestamp = self.clock.now if changed_at is None else changed_at
        self.values[entity_id] = SimpleNamespace(
            entity_id=entity_id, state=state, attributes={},
            last_changed=datetime.fromtimestamp(timestamp, timezone.utc),
        )
        for ids, listener in list(self.listeners):
            if entity_id in ids:
                listener(SimpleNamespace(data={'entity_id': entity_id, 'old_state': previous,
                                               'new_state': self.values[entity_id]}))


class FakeHass:
    def __init__(self, clock):
        self.clock = clock
        self.states = States(clock)
        self.calls = []
        self.service_calls = []
        self.events = []
        self.timers = []
        self.tasks = []
        self.data = {}
        self.zone_status = []
        self.zone_schedules = []
        self.auto_confirm = True
        self.fail_entities = set()
        self.services = SimpleNamespace(async_call=self.call)
        self.bus = SimpleNamespace(async_fire=lambda name, data: self.events.append((name, deepcopy(data))))

    async def call(self, domain, service, data, **kwargs):
        self.service_calls.append((domain, service, deepcopy(data), kwargs))
        entity = data.get('entity_id')
        self.calls.append((self.clock.now, service, entity))
        if entity in self.fail_entities:
            raise RuntimeError('Device command failed')
        if self.auto_confirm and service in ('turn_on', 'turn_off'):
            self.states.set(entity, 'on' if service == 'turn_on' else 'off')

    def async_create_task(self, coro, *, eager_start=True):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            coro.close()
            raise RuntimeError('hass.async_create_task called outside the event loop')
        if hasattr(asyncio, 'eager_task_factory'):
            task = asyncio.Task(coro, loop=asyncio.get_running_loop(), eager_start=eager_start)
        else:
            task = asyncio.create_task(coro)
        self.tasks.append(task)
        return task

    def call_later(self, hass, delay, fn):
        timer = [self.clock.now + delay, fn, False]
        self.timers.append(timer)
        return lambda: timer.__setitem__(2, True)

    def track_states(self, hass, ids, fn):
        item = (set(ids), fn)
        self.states.listeners.append(item)
        return lambda: self.states.listeners.remove(item)

    def track_interval(self, hass, fn, interval):
        active = True
        cancel = None

        async def run(now):
            nonlocal cancel
            if active:
                await fn(now)
                cancel = self.call_later(hass, interval.total_seconds(), run)

        cancel = self.call_later(hass, interval.total_seconds(), run)

        def remove():
            nonlocal active
            active = False
            cancel()
        return remove

    async def dispatch_due(self):
        for timer in list(self.timers):
            if timer[2] or timer[0] > self.clock.now:
                continue
            timer[2] = True
            fn = timer[1]
            if inspect.iscoroutinefunction(fn):
                await fn(None)
            elif getattr(fn, '_hass_callback', False):
                fn(None)
            else:
                await asyncio.to_thread(fn, None)


def zone(zid='noah', delta=0.3, **overrides):
    value = {
        'zone_id': zid, 'co_mode': 'HEAT', 'active_co_mode': 'HEAT',
        'delta_air': delta, 't_air': 22 - delta, 't_floor': None,
        'manual_off': False, 'eligible_window': True, 'support_mode': 'BOTH',
        'actuator': {'entity_id': f'switch.{zid}', 'open_s': 60, 'close_s': 60},
        'limits': {'zone_min_on_s': 180, 'zone_min_off_s': 180},
    }
    value.update(overrides)
    return value


def coordinator(config=None, zones=None):
    clock = Clock()
    hass = FakeHass(clock)
    namespace = dict(
        __name__='test_zone_manager', asyncio=SimpleNamespace(Task=asyncio.Task, Lock=asyncio.Lock, sleep=clock.sleep, CancelledError=asyncio.CancelledError, current_task=asyncio.current_task, gather=asyncio.gather),
        logging=logging, time=clock, timedelta=timedelta, callback=callback, deepcopy=deepcopy,
        async_call_later=hass.call_later,
        async_track_state_change_event=hass.track_states,
        async_track_time_interval=hass.track_interval,
        get_current_config=lambda entry: deepcopy(entry.config),
        co_mode_from_entity=lambda hass, options: options.get('test_mode', 'HEAT'),
        SERVICE_TURN_ON='turn_on', SERVICE_TURN_OFF='turn_off', HA_DOMAIN='homeassistant',
    )
    load_source('const.py', namespace)
    regulator_ns = dict(__name__='test_supply_regulator', asyncio=asyncio, logging=logging,
                        time=clock, THERMAL_UPDATE_SECONDS=60, Store=MemoryStore, SupplyController=supply_module.SupplyController,
                        finite=supply_module.finite, normalize_supply_config=supply_module.normalize_supply_config)
    load_source('supply_regulator.py', regulator_ns)
    namespace['SupplyRegulator'] = regulator_ns['SupplyRegulator']
    load_source('zone_manager.py', namespace)
    options = dict(namespace['DEFAULTS'], t_cycle_min=600, t_cycle_max=600)
    options.update(config or {})
    entry = SimpleNamespace(entry_id='test', config=options)
    manager = namespace['ZoneManager'](hass, entry)
    for value in zones or [zone()]:
        manager._zones[value['zone_id']] = value
        manager._zone_listeners[value['zone_id']] = lambda data, **kwargs: hass.zone_schedules.append(deepcopy(data))
        hass.states.set(value['actuator']['entity_id'], 'off', clock.now - 1000)
    return manager, hass, clock


class FakeOptionsFlow:
    def async_show_form(self, **kwargs):
        return dict(type='form', **kwargs)

    def async_create_entry(self, **kwargs):
        return dict(type='create_entry', **kwargs)


def options_flow():
    import voluptuous as vol

    namespace = dict(__name__='test_config_flow', vol=vol, callback=callback,
                     SUPPLY_DEFAULTS=supply_module.SUPPLY_DEFAULTS, finite=supply_module.finite,
                     normalize_supply_config=supply_module.normalize_supply_config,
                     config_entries=SimpleNamespace(OptionsFlow=FakeOptionsFlow),
                     selector=lambda config: lambda value: value)
    return load_source('config_flow.py', namespace, skip_classes=('ConfigFlow',))


class FakeClimateEntity:
    async def async_added_to_hass(self):
        pass

    async def async_get_last_state(self):
        return None


def thermostat(hass, entry, config, manager=None):
    if not hasattr(entry, 'entry_id'):
        entry.entry_id = 'test'
    if manager is None:
        manager = SimpleNamespace(
            async_set_zone_status=lambda data: hass.zone_status.append(deepcopy(data)),
            async_request_evaluation=lambda: None)
    hass.data.setdefault('virtual_climate', {})[entry.entry_id] = {'virtual_climate_manager': manager}
    namespace = dict(
        __name__='test_climate', logging=logging, timedelta=timedelta, callback=callback,
        monotonic=hass.clock.time, time=hass.clock.time, TemperatureFilter=filter_module.TemperatureFilter,
        ClimateEntity=FakeClimateEntity, RestoreEntity=type('RestoreEntity', (), {}),
        ClimateEntityFeature=SimpleNamespace(TARGET_TEMPERATURE=1),
        UnitOfTemperature=SimpleNamespace(CELSIUS='C'),
        ATTR_TEMPERATURE='temperature',
        HVACMode=SimpleNamespace(AUTO='auto', OFF='off'),
        HVACAction=SimpleNamespace(HEATING='heating', COOLING='cooling', IDLE='idle', OFF='off'),
        get_current_config=lambda entry: entry.config,
        co_mode_from_entity=lambda hass, options: options.get('test_mode', 'HEAT'),
        get_state_str=lambda hass, entity: hass.states.get(entity).state if hass.states.get(entity) else None,
        get_state_float=lambda hass, entity: supply_module.finite(hass.states.get(entity).state) if hass.states.get(entity) else None,
        dew_point_c=lambda temperature, humidity: temperature - (100 - humidity) / 5,
    )
    load_source('const.py', namespace)
    load_source('climate.py', namespace)
    return namespace['VirtualThermostat'](hass, entry, config)
