# Testing and development

## Regression suite

Use Python 3.10 or newer:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-test.txt
.venv/bin/python -m unittest discover -s tests -v
```

Tests exercise production coordinator, options-flow, climate, supply, and thermal
logic with controlled time and mocked Home Assistant services/state storage.
Schema validation uses real Voluptuous. Coverage includes cycle boundaries,
minimum timing, output feedback, zone transfers, circuit ownership, filtering,
configuration persistence, and failed writes.

These are not a full Home Assistant integration-loading test or proof of physical
actuator/flow behavior. Verify those separately when validating equipment;
publish only generic, non-identifiable findings.

## Thermal simulations

```sh
.venv/bin/python simulations/thermal_acceptance.py
```

This uses synthetic plants and writes Markdown and JSON under
`docs/development/observations/`. Review both favorable and unfavorable scenarios.
The [recorded report](observations/thermal-simulation-results.md) explains the
method and unmet acceptance criteria. Regenerate it when the simulated policy
changes and identify the source revision in the report.

## Deployment helpers

`dev/sync.sh` and `dev/deploy.py` support SSH deployment to a user-supplied host.
They are contributor tools rather than prerequisites for using the integration.
Use `bash dev/sync.sh --help` for options and host requirements. Supply your own
host/configuration path; no installation-specific deployment configuration is
part of the public documentation.

The deploy helper tests an immutable source snapshot, backs up installed code
and integration configuration, stages files, checks hashes/syntax/imports, checks
Home Assistant configuration, and restarts Core unless `--no-restart` is selected.
API readiness after restart does not establish that every integration loaded or
that physical outputs behaved correctly. Inspect integration loading and feedback.

Backups are retained below `<config>/virtual_climate_backups/<backup-id>/`.
Code rollback does not overwrite Home Assistant's `.storage`; persisted
configuration backups are private reference material. Local deployment metadata
belongs in ignored `local/deployments/`.

## Documentation checks

Verify local Markdown links, JSON syntax and configuration schema, documented
keys/defaults against the source, and `git diff --check`. Update guides when
behavior changes and check that generated reports retain the agreed language
and structure. See the [documentation policy](documentation-policy.md).
