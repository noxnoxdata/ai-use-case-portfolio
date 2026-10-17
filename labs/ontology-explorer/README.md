# Ontology Explorer

A single HTML page that makes the use case ontology tangible.

Click a class and see:
- its description,
- the properties that connect it to other classes,
- related classes in a small relationship diagram,
- instances where relevant (data sources and their entities, risk tiers, buckets, gates).

## Why

An ontology is hard to hold in your head. A list of classes and properties reads like a dictionary. This lets you click around the meaning instead.

## Build

```bash
python3 build.py
```

Writes `index.html`, self-contained (the ontology is embedded, so it works from `file://`).

Optional:

```bash
python3 build.py --ontology ../../ontology/use_case_ontology.json
```

## Notes

- No external libraries, no network calls.
- It reads whatever ontology you point it at, as long as the shape matches.
- It is a viewer, not an editor.
