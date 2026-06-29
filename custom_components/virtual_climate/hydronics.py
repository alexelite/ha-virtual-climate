from __future__ import annotations

import logging
from homeassistant.core import HomeAssistant, callback
from .const import EVT_HYDRONICS_DEMAND

_LOGGER = logging.getLogger(__name__)

class HydronicsRegulator:
    """Optional regulator that listens for EVT_HYDRONICS_DEMAND and
    translates demand_ratio + dew caps into a target supply temperature or valve %.
    MVP: stub only.
    """
    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._unsub = None

    async def async_start(self):
        self._unsub = self.hass.bus.async_listen(EVT_HYDRONICS_DEMAND, self._on_demand)

    async def async_stop(self):
        if self._unsub:
            self._unsub()
            self._unsub = None

    @callback
    def _on_demand(self, event):
        data = event.data or {}
        _LOGGER.debug("Hydronics demand: %s", data)
        # TODO: map demand -> number.tur_target or valve percentage
