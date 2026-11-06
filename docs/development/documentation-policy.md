# Documentation policy

## Purpose and language

Public documentation describes the integration available in the corresponding
source revision. Write it in English, for Home Assistant users first. UI
translations remain supported; configuration identifiers retain their exact
spelling from the code.

Documentation on `main` describes `main`. Documentation in a release tag
describes that release. Separate versioned documentation hosting is unnecessary
until there is a demonstrated need.

## Target structure

Adopt this structure as existing documentation is reorganized. Create pages
when their content warrants them; this policy does not require empty files.

```text
README.md
CHANGELOG.md
CONTRIBUTING.md
GLOSSARY.md
docs/
  getting-started.md
  configuration.md
  operation.md
  troubleshooting.md
  features/
    supply-control.md
    external-circuit.md
    temperature-fallback.md
    adaptive-control.md
  reference/
    configuration.md
    diagnostics.md
  development/
    documentation-policy.md
    testing.md
    observations/
  adr/
```

| Location | Responsibility |
| --- | --- |
| README | Purpose, suitability, prerequisites, installation entry point, and guide links |
| Getting started | Installation and a minimal working first zone |
| Configuration | UI choices and their effects; advanced JSON examples follow UI instructions |
| Operation | Normal zone and circuit behavior, including responsibility boundaries |
| Troubleshooting | Symptoms, checks, explanations, and remedies |
| Features | Enabling and using each optional feature, with its specific limitations |
| Reference | Configuration keys, defaults, units, and diagnostic semantics |
| Development | Contribution workflows, testing, and reproducible validation evidence |
| ADRs | Architectural decisions and their rationale |
| Changelog | User-relevant differences between releases and migration notices |

Keep one authoritative explanation for each fact. Link to reference tables
instead of copying defaults and diagnostic definitions into several guides.
The README introduces the product rather than duplicating its manual.

## Updating documentation with code

Update affected sections as part of a change to user-visible behavior. Assess
documentation impact before considering the change complete. Rewrite only the
affected explanations; a commit does not require a documentation rewrite.

| Change | Documentation action |
| --- | --- |
| Internal refactor with unchanged behavior | Usually none |
| New or changed setting | Update the feature guide and configuration reference |
| Changed behavior | Update operation or feature documentation and affected troubleshooting |
| Bug fix | Record the user-relevant fix in the changelog; correct any inaccurate instructions or obsolete workaround |
| Breaking change | Update guides and reference, provide migration instructions, and record the change in the changelog |
| Experiment or test result | Use an issue or observation report; update guides when a confirmed limitation affects users |
| Release | Consolidate changelog entries and check that documentation matches the released behavior |

The changelog records what changed. Guides explain how the current version
works, without requiring readers to reconstruct behavior from release history.
Before release, user-relevant changes can accumulate under an Unreleased
section; consolidate them into the release entry rather than listing every
commit.

## Editorial rules

- Describe current, verifiable behavior in the present tense. Keep plans and
  proposed features in issues until implemented and documented.
- Use generic, self-contained examples. Personal or test installation names,
  real entity IDs, hardware inventories, deployment procedures, and identifiable
  installation reports do not belong anywhere in this repository. Keep raw
  installation evidence outside the repository. Synthetic test fixtures and
  generic hardware requirements are appropriate.
- Explain prerequisites and the boundary between integration responsibilities
  and device responsibilities before advanced configuration details.
- State limitations for the specific feature they affect. An experimental label
  must explain its practical meaning, such as explicit opt-in or unmet
  validation criteria. Installation status in the author's environment does
  not establish product readiness.
- Keep dated deployment status, session handovers, conversational approvals,
  and implementation narratives out of user guides. Avoid relative claims such
  as “now implemented” and unsupported readiness claims.
- Use terminology consistently with the glossary and exact UI labels where
  relevant. Explain unfamiliar concepts before relying on them.
- Distinguish reported software state from physical confirmation wherever this
  affects interpretation or configuration. Define the distinction centrally
  and link to it where needed.
- Keep test names, debugging history, and agent instructions in development
  documentation rather than user guides.

## Issues, observations, and decisions

Use GitHub issues for bugs, proposals, and investigations requiring action or a
decision, following the repository's issue-tracker instructions. Community
ideas remain proposals until evaluated; they are not README promises.

Preserve substantial, reproducible findings in `docs/development/observations/`.
Each report identifies its date, version or commit, generic conditions,
method, results, and limits of the conclusion. Generalize and anonymize real
installation observations before publication, removing installation-specific
references entirely. Preserve unfavorable results as well as favorable ones.

Promote confirmed user-facing conclusions into the relevant guide. Record
architectural decisions in ADRs. Historical observations remain scoped to the
revision and conditions they tested rather than becoming timeless product
claims.

## Review criteria

A documentation change is complete when instructions and claims match the
relevant code, examples use supported keys and generic identifiers, local links
resolve, and existing explanations affected by the change have been updated
or removed. Report the scope of validation accurately; tests and simulations
support only the conclusions they actually establish.
