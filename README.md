# NIKKE Squad Calculator

A static squad damage calculator that runs the existing Python simulation engine inside a web browser.

Service: <https://moris-kr.github.io/nikke-calc/>

Original calculation engine: <https://github.com/Jgaram/nikke-calc>

## Structure

- `calculator/`, `context/`, `data/`: Calculation engine and source data
- `site/`: Static web application built with Vite and TypeScript
- `site/public/calculator.worker.js`: Web Worker that isolates calculations from the UI to execute them sequentially
- `site/pybridge/bridge.py`: Bridge converting web requests into calls to the existing Python engine
- `site/scripts/sync-runtime.mjs`: Synchronizes the engine, data, character lists, and images to the web runtime
- `worker/`: BlaBla Link lookup proxy (Cloudflare Workers). Deployed separately from the main site
- `.github/workflows/pages.yml`: Automation workflow for testing, building, and deploying to GitHub Pages

## Key Features

- Individual customization for each character: Overload Gear, Harmony Cubes (17 types), Favorite Items/Collectibles, Skill Levels, Limit Breaks, and Control settings
- Account Console Settings — Applies shared stats, 3 class types, and 5 manufacturer types per affiliation to the entire squad
- 5-Deck Mode & Deck Copying — Easily duplicate a deck's setup and configuration to another slot to compare different main DPS characters
- Character-specific Normal/Skill Damage Breakdown — Displays contribution percentages, normal attack vs. skill damage ratios, and per-skill damage and hit counts
- Frame-by-frame combat timeline graph
- Report Image Generation — Export results into a single PNG image to copy or save (1-deck mode generates a vertical card, while 5-deck mode compiles totals and individual damage for all 25 characters into one image)
- Burst Gauge Charge Time Adjustment — Override automatic gauge accumulation by manually entering a fixed charge time to tune cycle timings
- Real-time roster sync via LetsDoro CSV import or BlaBla Link profile integration
- Share squads via links or codes, save squad presets, and compare performance rankings across decks

The web app runs the Python engine inside a Web Worker using a fixed version of Pyodide. All calculation requests and results remain strictly within the user's browser, utilizing no AI APIs, dedicated backend servers, databases, user logins, or analytics tools. A cache storing up to 30 calculation results is saved locally in the browser's localStorage.

The current selection list only includes characters that exist in both data/parsed_nikke.json and data/parsed_skills.json. Test entries (test_) are excluded, and unreleased preview characters display a warning indicating unverified data. A total of 199 characters are supported based on the current sync release.

## Local Running

Requires Node.js 22 or higher and Python 3.

```bash
cd site
npm install
npm run dev
```

Open the /nikke-calc/ path at the local URL provided by Vite. Internet access is required for the initial run to download Pyodide, after which it relies on the browser cache.

## Verification

Quick verification for the web application::

```bash
cd site
npm test -- --run
python3 scripts/test-bridge.py
npm run check-pages
npm run build
```

Full verification, including the original calculation engine:

```bash
python3 calculator/damage.py
python3 -m context.doclint
python3 -m context.snapshot
```

## Data Syncing

When the engine, data, or character images are updated, do not edit generated build artifacts directly. Re-sync them using the following commands:

```bash
cd site
npm run sync-runtime
npm run check-runtime
```

Executing npm run dev and npm run build will also automatically trigger runtime synchronization prior to execution.

## Deployment

Pushing to the master branch triggers GitHub Actions to install dependencies according to the lockfile. Once tests and production builds pass, site/dist is deployed to GitHub Pages. The default Vite deployment base path is /nikke-calc/.

### BlaBla Link Integration (Optional)

Retrieving user build data via profile URLs requires a proxy server, as the BlaBla Link API does not enable CORS and requires an active login session for queries, making direct client-side calls impossible for a static site.
Deployment instructions are available in worker/README.md. Assigning the deployed URL to VITE_BLABLA_PROXY in site/.env.production will render the BlaBla Link Integration button on the site. Leaving this variable blank suppresses the button, leaving only the LetsDoro CSV import option.

## License

The original calculation engine is hosted at https://github.com/Jgaram/nikke-calc and released under the MIT License.
As a fork, this repository operates under the same MIT License, retaining the original copyright notice in the LICENSE file.

    Copyright (c) 2026 Jgaram
    MIT License

## Disclaimer

This repository and service are unofficial fan-made tools and are not affiliated with, endorsed by, or sponsored by SHIFT UP or Level Infinite.
All rights regarding game data, characters, images, and related assets from "GODDESS OF VICTORY: NIKKE" belong exclusively to SHIFT UP CORP. and Level Infinite.
The license above applies strictly to the calculator codebase and does not cover game assets.
Before hosting or operating publicly, please verify distribution permissions for all used assets and data independently.

Calculation outputs are provided for reference only — edge-case bugs or unverified in-game mechanics may still exist.
