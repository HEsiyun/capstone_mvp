# DB_SCHEMA.md (Prototype)

## Tables

### assets
- asset_id (TEXT, PK)
- type (TEXT) -- e.g., playground, bench, trail, parking_lot
- sub_type (TEXT) -- e.g., slide, swing, asphalt, gravel
- park_id (TEXT)
- park_name (TEXT)
- lon (FLOAT)
- lat (FLOAT)
- geom_wkt (TEXT, SRID:4326 POINT)
- install_date (DATE)
- criticality (TEXT) -- low|medium|high
- last_visit_at (DATE)

### asset_condition
- asset_id (TEXT, FK -> assets.asset_id)
- assessed_at (DATE)
- source (TEXT) -- manual|cv
- condition (TEXT) -- good|fair|poor|unknown
- score (FLOAT) -- 0..1, higher is better
- notes (TEXT)

### asset_photos
- asset_id (TEXT, FK -> assets.asset_id)
- photo_id (TEXT, PK)
- uri (TEXT) -- file:// or s3://
- taken_at (DATE)
- taken_by (TEXT)
- labels_json (TEXT)

### costs
- asset_id (TEXT, FK -> assets.asset_id)
- replacement_cost (INT)
- last_updated_at (DATE)

## Read-only Views (recommended)
- v_assets_latest_condition: join assets with most recent condition per asset
- v_assets_with_costs: join assets with costs

## Allowed SQL patterns
- SELECT ... FROM assets JOIN asset_condition ... LEFT JOIN costs ...
- WHERE type=?, sub_type=?, ST_Intersects(geom, ...), assessed_at < NOW() - INTERVAL 'N days'
- LIMIT enforced; no writes allowed.
