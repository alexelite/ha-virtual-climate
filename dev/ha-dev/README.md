# Local Home Assistant development

Run these commands from the worktree root with Docker running:

```sh
python3 dev/ha-dev/prepare.py
HA_VERSION=stable docker compose -f dev/ha-dev/compose.yaml up -d
```

Use an explicit release instead of `stable` for repeatable compatibility checks.
The container is available at <http://localhost:8124>. Complete onboarding with
a development-only account. Do not connect real equipment or restore a production
backup. The container uses bridge networking, no device mounts, and a loopback-only
published port; these choices do not prevent outbound network access.

The preparation script creates synthetic helpers, sensors and switches. It leaves
an existing `configuration.yaml` untouched. All persistent runtime files live in
the ignored `local/ha-dev/` directory. Integration code is mounted read-only from
this worktree.

Add Virtual Climate twice through **Settings → Devices & services → Add
integration**. Choose the full JSON setup and paste each generated payload:

- `local/ha-dev/circuit-a.json`: direct control, two zones, weather compensation.
- `local/ha-dev/circuit-b.json`: external control, two zones, constant supply.

Rename the entries Circuit A and Circuit B. Both mode helpers start at `OFF`.
Select `HEAT` on one helper to exercise that entry. Change the room, outdoor,
supply and return input numbers to vary readings. Switches mirror input booleans
immediately; they simulate software feedback, not physical hydronics. Manual
temperature changes do not simulate a thermal response over time.

Restart after Python or panel JavaScript changes, then refresh the browser.
The panel has no frontend build step. Its resource URL includes a content version
computed at HA startup so browsers can load updated code. Inspect loading errors:

```sh
HA_VERSION=stable docker compose -f dev/ha-dev/compose.yaml restart
HA_VERSION=stable docker compose -f dev/ha-dev/compose.yaml logs --tail 100
HA_VERSION=stable docker compose -f dev/ha-dev/compose.yaml exec homeassistant python -m homeassistant --script check_config --config /config
HA_VERSION=stable docker compose -f dev/ha-dev/compose.yaml exec homeassistant python -m homeassistant --version
```

Stop with `docker compose ... stop` using the same file and `HA_VERSION`.
State persists across container recreation. Use the regression tests and thermal
simulations described in [Testing](../../docs/development/testing.md) alongside
this environment.
