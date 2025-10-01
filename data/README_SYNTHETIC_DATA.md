# Synthetic Urban Park Dataset (Prototype)

This folder contains a small synthetic dataset to prototype the Multimodal RAG system:

- assets.csv — point assets with WKT geometry, types, criticality, last visit date.
- asset_condition.csv — most recent condition per asset (simulated), scores and notes.
- asset_photos.csv — one photo per asset, with local file URI and optional labels.
- costs.csv — replacement cost estimates per asset.
- parks.geojson — three demo park polygons (rough boxes near Vancouver).
- kb_manuals.jsonl — small SOP/maintenance manual snippets for RAG.
- kb_policies.json — thresholds and weights for inspection and prioritization.
- DB_SCHEMA.md — the read-only schema contract for text-to-SQL generation.

Notes:
- Geometries are synthetic and for demo only.
- Image files in sample_images/ are placeholders.
