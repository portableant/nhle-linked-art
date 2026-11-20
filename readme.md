# NHLE Linked Art 1.0 Explorer & Static API

A zero-backend GitHub Pages static API and interactive explorer that transforms **Historic England** National Heritage List for England (NHLE) CSV exports into valid **[Linked Art v1.0](https://linked.art/) JSON-LD 1.1** knowledge graphs, complete with **Getty AAT** material alignments, **OSGB36-to-WGS84** coordinate conversion, **Wikidata** exact-match linking (`wdt:P1216`), and [`@micropasts/linked-art-viewer`](https://github.com/micropasts/linked-art-viewer).

---

## Features

- **Zero-Dependency Python Pipeline (`build_linked_art.py`):**
  - Uses only the Python 3.9+ standard library (`csv`, `json`, `math`, `re`, `urllib`)—requiring no third-party packages at build time.
  - **Linked Art v1.0 JSON-LD 1.1 Shards:** Emits sharded REST-style endpoints at `/api/object/{prefix}/{list_entry}.json` plus a faceted index at `/api/index/catalog.json`.
  - **OSGB36 → WGS84 Coordinate Transformation:** Converts British National Grid `Easting` and `Northing` (`EPSG:27700`) coordinates into WGS84 `POINT(lon lat)` WKT strings under `current_location.defined_by` using an Airy 1830 inverse Transverse Mercator and 7-parameter Helmert transformation.
  - **Getty AAT Fabric & Material Mapping (`made_of`):** Extracts historic building materials from listing descriptions (e.g., *Limestone*, *Clunch*, *Flint*, *Brick*, *Wood/Timber*, *Lead*, *Slate*, *Tile*, *Iron*) and links them to Getty Art & Architecture Thesaurus URIs.
  - **Multi-Phase Chronology (`produced_by` & `modified_by`):** Extracts named architects/builders (e.g., *William Huckvale*) and historical phases (explicit years and centuries) into `Production`, `Modification`, `Person`, and `TimeSpan` nodes.
  - **Exact-Match Wikidata & Outbound Links (`equivalent` & `subject_of`):** Batch-queries Wikidata SPARQL on `wdt:P1216` (NHLE List Entry Number) to attach Wikidata QIDs, English Wikipedia articles, Wikimedia Commons categories (`wdt:P373`), Geograph UK photo pages (`wdt:P1261`), and Wikimedia Commons `P18` images (`representation`).
- **Viewer-First Web Explorer (`index.html`):**
  - **Faceted Search & Filtering:** Filter by keyword (building name, NGR, locality, architect), Statutory Grade, Normalized Locality, Getty AAT Material, Architect/Maker, Historical Period, or Wikimedia Commons image availability.
  - **Deep-Linkable HTML URLs:** Selecting any asset updates the browser URL (`?id=<nhle_id>`) and page title via `history.pushState`, supporting direct links, bookmarks, and browser Back/Forward navigation.
  - **Live NHLE ID Resolver:** Resolves any NHLE List Entry Number—checking local `/api/object/` shards first and falling back to Historic England's public ArcGIS Listed Buildings REST service and Wikidata SPARQL.
  - **Rich Context Panel:** Displays Wikimedia Commons photography (with lightbox and license/file links), a synchronized MapLibre GL mini-map, a semantic Linked Art dossier, and an interactive horizontal **Chronology & Statutory Lifecycle** timeline.
  - **Embedded Network & Data Inspector:** Mounts `@micropasts/linked-art-viewer` for synchronized D3 force-directed graph, collapsible JSON tree, raw JSON-LD, and RDF N-Quads inspection.
  - **Guided Tour & OGL v3.0 Notice:** Includes an interactive **Intro.js** guided tour and a dismissible Open Government Licence v3.0 attribution and non-endorsement modal.

---

## Repository Structure

```text
.
├── .github/
│   └── workflows/
│       └── deploy.yml                  # Automated GitHub Actions build & Pages deployment
├── api/
│   ├── index/
│   │   └── catalog.json                # Faceted search & filter index
│   └── object/
│       └── {prefix}/
│           └── {list_entry}.json       # Sharded Linked Art 1.0 JSON-LD records
├── build_linked_art.py                 # Zero-dependency CSV -> Linked Art 1.0 converter
├── historic_england_sample_10th.csv    # Sample NHLE dataset
├── index.html                          # Viewer-first GitHub Pages web application
└── README.md
```

---

## Quick Start

### 1. Generate Linked Art JSON-LD Shards Locally

Run `build_linked_art.py` against your Historic England CSV export:

```bash
python3 build_linked_art.py \
  --input historic_england_sample_10th.csv \
  --output ./api \
  --base-url "https://portableant.github.io/nhle-linked-art"
```

#### CLI Options

| Flag | Default | Description |
| :--- | :--- | :--- |
| `--input` | *(required)* | Path to the Historic England NHLE CSV file. |
| `--output` | `./api` | Output directory for `object/{prefix}/{id}.json` shards and `index/catalog.json`. |
| `--base-url` | `https://portableant.github.io/nhle-linked-art` | Base URI used for generated Linked Art `@id` URIs. |
| `--skip-wikidata` | `false` | Skip live Wikidata SPARQL `wdt:P1216` enrichment during offline builds. |

### 2. Preview Locally

Serve the directory over HTTP so `fetch()` requests to `./api/` resolve cleanly:

```bash
python3 -m http.server 8000
```

Open `http://localhost:8000/` (or `http://localhost:8000/?id=1083558` for a direct entity link).

### 3. Deploy to GitHub Pages

1. Push this repository to GitHub on the `main` branch.
2. Go to **Settings → Pages → Build and deployment** and set **Source** to **GitHub Actions**.
3. The included workflow (`.github/workflows/deploy.yml`) will automatically run `build_linked_art.py` and publish the static Linked Art API and web interface to GitHub Pages.

---

## Expected CSV Schema

`build_linked_art.py` supports standard Historic England NHLE CSV exports containing:

- `List Entry Number` (or `ListEntry`)
- `List Entry Name` (or `Name`)
- `Grade` (`I`, `II*`, `II`, `SM`)
- `Listing date` & `Date of most recent amendment`
- `Capture scale` & `NHLE link`
- `National Grid Reference`, `Easting`, `Northing` (or `Latitude`, `Longitude`)
- `Summary`, `Reasons for Designation`, `History`, `Details`, `Legacy`, `Selected Sources`

---

## Data Attribution & Licence

- **Source Data:** Contains Historic England National Heritage List for England (NHLE) data © Historic England, licensed under the [Open Government Licence v3.0 (OGL v3)](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/). This project is an independent open-data prototype and is **not endorsed by Historic England**.
- **Linked Vocabularies & External Data:** Material URIs reference the [Getty Art & Architecture Thesaurus (AAT)](https://www.getty.edu/research/tools/vocabularies/aat/) (ODC-By 1.0); external entity links and imagery metadata are retrieved from [Wikidata](https://www.wikidata.org/) (CC0) and [Wikimedia Commons](https://commons.wikimedia.org/).
