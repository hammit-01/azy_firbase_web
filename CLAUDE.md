# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

A warehouse inventory management system for a cold-storage logistics company. It crawls inventory data from multiple warehouse websites, processes it with Python/pandas, uploads to Firebase Firestore, and displays it through a vanilla JS web app.

Full data flow: **크롤링 (web scraping) → EDA (Python/pandas) → Firestore upload (post.py) → Web UI (HTML/JS/Firebase SDK)**

## Running the Backend

```bash
# Run the full pipeline: crawl → EDA → output to jns.xlsx
python main.py

# Upload processed data to Firestore (uncomment the post(jns) line in main.py first)
python main.py  # with post(jns) uncommented
```

The Firebase Admin SDK credential file (`azy7503-d80d9-firebase-adminsdk-fbsvc-*.json`) is gitignored — it must be present locally to run `post.py`.

`back_eda_main.py` has a hardcoded `sys.path.append` pointing to `C:\Users\ASUS\.vscode\azy_firbase_web` — update this if running on a different machine.

## Serving the Frontend

The frontend is plain HTML/JS with no build step. Serve `front_end/html/warehouse_main.html` via a local HTTP server (required for ES module imports):

```bash
# From the project root
python -m http.server 8000
# Then open: http://localhost:8000/front_end/html/warehouse_main.html
```

Firebase is loaded via CDN (version `12.12.0`) — no npm install needed.

**Important:** HTML file paths differ by serving context (comment at top of `warehouse_main.html`):
- Firebase Hosting: use `/css/...`
- Local Python server: use `./css/...`

## Firebase Project

- Project ID: `azy7503-d80d9`
- Firestore collection: `all_data`
- Firestore rules: currently open (`allow read, write: if true`) — no auth enforced
- Free tier limit: ~1000 reads/writes per day before throttling

## Architecture

### Backend (`back_end/`)

| File | Purpose |
|---|---|
| `crawling_list.py` | HTTP scraping of warehouse sites (login → data fetch per site) |
| `crawling_handmade.py` | Manual scraping for sites that don't follow the standard pattern |
| `back_eda_main.py` | Orchestrates EDA pipeline; calls site-specific EDA functions |
| `eda_ch_plz_cs.py` | EDA for CH, PLZ, CS warehouses |
| `eda_else_df.py` | EDA for other warehouses |
| `jns_eda.py` | EDA specific to 제니스(JNS) |
| `eda_standard.py`, `eda_common.py`, `eda_added.py`, `eda_column.py` | Shared EDA utilities |
| `replace_name.py` | Product name normalization/standardization |
| `equal_df.py` | Diffs new crawled data against existing inventory spreadsheet (`[창고]재고장(전미림).xlsx`), flagging rows as `new`, `deleted`, or `!` (quantity changed) |
| `exception_safe.py` | Safe wrappers for EDA functions |
| `data/` | Output Excel files consumed by the web UI or used as comparison baselines |

`post.py` (project root): standalone Firestore uploader. Converts DataFrame rows to Firestore documents with a composite `pk` key of `{BL_last4}_{expire_date}_{weight}`.

### Frontend (`front_end/html/`)

Single-page app with no framework. Entry point: `warehouse_main.html`.

**JS module responsibilities:**

| File | Role |
|---|---|
| `state.js` | Single source of truth: `state.allData` (all items), `state.selectedItems` (Map of checked rows), `state.flashIds`, `state.crudData` |
| `firebase.js` | Firebase init + `subscribeData()` — sets up the real-time Firestore listener that populates `state.allData` and triggers re-render |
| `firestoreService.js` | Direct Firestore CRUD: `insertItem`, `updateItem`, `deleteItem`, `getItems` |
| `table.js` | Renders the inventory table; reads `state.allData`, applies search filter and sort |
| `panel.js` | Renders the right-side action panel: `renderSelectData`, `renderInsert`, `renderUpdate`, `renderHolding`, `renderFooter` |
| `events.js` | `bindEvents()` — all DOM event listeners (click, change, input) |
| `crud.js` | Business logic: `holdingData`, `insertData`, `updateData`, `deleteItem` — writes to Firestore via `firestoreService.js` |
| `crud_history.js` | Undo stack (`undoStack`) and `undoLastAction()` |
| `data_eda.js` | Normalizes raw Firestore item fields into UI-friendly shape; `addSelectedItem()` |
| `dom.js` | Cached DOM element references |
| `input_calculater.js` | `calculateTotal()` for holding qty/weight input boxes |
| `actions.js` | Panel mode enum/constants |

**Rendering flow:**
1. `warehouse_main.html` loads → `bindEvents()` → `initFirebase()` → `subscribeData()`
2. Firestore snapshot arrives → `state.allData` updated → `renderTable()` + `renderSelectData()`
3. Checkbox click → `addSelectedItem()` → `state.selectedItems` updated → `renderAll()`
4. Panel actions (holding/insert/update/delete) → `crud.js` → `firestoreService.js` → Firestore write → snapshot triggers re-render

**Item identity:** rendering uses display fields (상품명, 브랜드, etc.); all Firestore operations use `item.id` (auto-generated Firestore document ID).

## Key Data Fields (Firestore document schema)

`상품명`, `브랜드`, `등급`, `ESTNO`, `재고` (int), `BL`, `창고`, `유통기한` (YYYY-MM-DD), `중량` (float), `평중` (float), `출고일`, `홀딩` (bool or string), `상태` ("없음" | "holding"), `메모`, `상이`, `수집일`, `pk`, `id`
