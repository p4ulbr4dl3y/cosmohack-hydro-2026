# Hydro-Monitoring CosmoHack 2026

Operational Sentinel-1 (SAR) and Sentinel-2 (MSI) hydrological monitoring service for the Amur River Basin (11 AOI pairs).

## Features

- **FastAPI Service (`src/service/app.py`)**:
  - `GET /api/v1/health`: Health status check.
  - `GET /api/v1/pairs`: Lists 11 pairs with AOI metadata, dates, areas.
  - `GET /api/v1/report/{pair_id}`: Automated summary report (`flood_ha`, `flood_km2`, `water_pre_ha`, `water_peak_ha`, `receded_ha`, `water_gain_ha`, `water_gain_pct`, `share_of_aoi`, and ESA WorldCover built-up / natural landcover breakdown).
  - `GET /api/v1/report/{pair_id}/csv`: CSV report export endpoint.
  - `GET /api/v1/geojson/{pair_id}`: EPSG:4326 vector polygons (layers: `flood`, `water_pre`, `water_peak`).
  - `POST /api/v1/predict`: Spatial-temporal inference by pair ID or bounding box `[min_lon, min_lat, max_lon, max_lat]`.
  - Static mount: Interactive Leaflet dashboard at root `/`.

- **Interactive Web Dashboard (`src/service/static/index.html`)**:
  - Leaflet web map with Esri World Imagery and OpenStreetMap basemap switcher.
  - Flood zone highlight (red / cyan toggle).
  - Water Pre and Water Peak layer toggles with popups.
  - Metric cards: flood area (ha, km²), water gain %, flood share %.
  - Chart.js breakdown of flooded land cover types (ESA WorldCover & JRC GSW).
  - One-click GeoJSON and CSV export buttons.

## Running the Service

### Option 1: Local with uv (Recommended)

```bash
# Install dependencies
uv sync

# Run FastAPI server
uv run uvicorn src.service.app:app --host 0.0.0.0 --port 8000
```

Access the UI at `http://localhost:8000` and Swagger API docs at `http://localhost:8000/docs`.

### Option 2: Docker / Docker Compose

```bash
# Build and run with Docker Compose
docker compose up --build

# Or build and run with Docker directly
docker build -t hydrowatch-service .
docker run -p 8000:8000 hydrowatch-service
```

### Running Tests

```bash
uv run pytest
```
