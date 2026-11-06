# Contributing

Use [GitHub Issues](https://github.com/alexelite/ha-virtual-climate/issues) for bugs,
feature proposals, and investigations. Describe the problem and expected behavior
before proposing a solution. Ideas are evaluated individually and do not become
release commitments merely by being recorded.

Include integration/Home Assistant versions and generic reproduction steps.
Remove personal installation names, real entity IDs, and identifiable logs or
configuration. Keep raw installation evidence outside this repository.

Before changing code, consult the [glossary](GLOSSARY.md) and relevant
[architectural decisions](docs/adr/). Use the [testing guide](docs/development/testing.md)
for local checks.

Follow the [documentation policy](docs/development/documentation-policy.md).
Changes to user-visible behavior include updates to the affected guide/reference
and a user-relevant changelog entry where appropriate. Internal refactors do not
require documentation churn. Guides describe current behavior; issues track
proposals and the changelog records release differences.

Keep reproducible, generic validation reports in
[development observations](docs/development/observations/). Identify revision,
conditions, method, results, and limitations, including unfavorable results.
