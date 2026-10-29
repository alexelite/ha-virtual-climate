# Domain docs

## Read before exploring

This repository uses a single-context layout.

- Read root `GLOSSARY.md` before exploring domain concepts.
- Read decisions in `docs/adr/` that concern the area being changed.
- If these documents do not exist, proceed silently. The domain-modeling skill creates them when terms or decisions are resolved.

## Layout

```text
/
├── GLOSSARY.md
├── docs/
│   └── adr/
│       └── <number>-<decision>.md
└── custom_components/
    └── virtual_climate/
```

## Vocabulary

Use glossary terms in code, tests, issue titles, hypotheses, and proposals. If a needed concept is missing, consider whether it belongs in the existing vocabulary or should be resolved through domain-modeling.

## Decisions

Surface conflicts with existing ADRs explicitly, citing the ADR and explaining why the decision should be reconsidered.
