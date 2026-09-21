// Stages the runtime data assets that the SPA loads (either from the API or as an
// offline fallback) into frontend/public, so `vite build` can emit them into
// src/service/static/ (which is wiped by emptyOutDir on every build).
//
// Canonical sources stay in the repository's single data tree (hydrowatch_amur/);
// the copies under frontend/public are generated and therefore git-ignored:
//
//   vendor/          <- src/service/static/vendor   (Leaflet, Font Awesome, fonts)
//   icons/           <- src/service/static/icons    (branding / report illustrations)
//   data/*.geojson   <- hydrowatch_amur/vectors
//   data/pairs.csv   <- hydrowatch_amur/pairs.csv
//   data/events_catalog.json <- hydrowatch_amur/tables/events_catalog.json
import { cp, mkdir, rm, stat } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, '../..');
const publicDir = path.resolve(here, '../public');

const vendorSource = path.join(repoRoot, 'src/service/static/vendor');
const iconsSource = path.join(repoRoot, 'src/service/static/icons');
const dataDir = path.join(publicDir, 'data');

const DATA_FILES = [
  ['hydrowatch_amur/vectors/amur_oblast.geojson', 'amur_oblast.geojson'],
  ['hydrowatch_amur/vectors/aoi.geojson', 'aoi.geojson'],
  ['hydrowatch_amur/vectors/basins_hydrosheds.geojson', 'basins_hydrosheds.geojson'],
  ['hydrowatch_amur/vectors/hydrography_osm.geojson', 'hydrography_osm.geojson'],
  ['hydrowatch_amur/pairs.csv', 'pairs.csv'],
  ['hydrowatch_amur/tables/events_catalog.json', 'events_catalog.json'],
];

const missing = [];

if (!existsSync(vendorSource)) {
  missing.push(vendorSource);
}
if (!existsSync(iconsSource)) {
  missing.push(iconsSource);
}
for (const [source] of DATA_FILES) {
  const abs = path.join(repoRoot, source);
  if (!existsSync(abs)) missing.push(abs);
}

if (missing.length > 0) {
  console.error('[sync-assets] missing source paths:');
  for (const m of missing) console.error(`  - ${path.relative(repoRoot, m)}`);
  console.error(
    'Restore the committed offline assets with:\n' +
      '  git checkout -- src/service/static/vendor src/service/static/icons'
  );
  process.exit(1);
}

// vendor/ -> public/vendor/
const vendorTarget = path.join(publicDir, 'vendor');
await rm(vendorTarget, { recursive: true, force: true });
await cp(vendorSource, vendorTarget, { recursive: true });

// src/service/static/icons -> public/icons/
const iconsTarget = path.join(publicDir, 'icons');
await rm(iconsTarget, { recursive: true, force: true });
await cp(iconsSource, iconsTarget, { recursive: true });

// canonical data tree -> public/data/
await rm(dataDir, { recursive: true, force: true });
await mkdir(dataDir, { recursive: true });
for (const [source, name] of DATA_FILES) {
  await cp(path.join(repoRoot, source), path.join(dataDir, name));
}

const leaflet = await stat(path.join(vendorTarget, 'leaflet', 'leaflet.js'));
console.log(
  `[sync-assets] public/{vendor,icons} + ${DATA_FILES.length} data files refreshed ` +
    `(${leaflet.size} B leaflet.js)`
);