# BrickBot: Lego Set Rebuild Helper — Data & App Plan

*This is the design plan that was reviewed and approved before any code was written. Kept as-is for reference; see "Implementation notes" at the bottom for where the shipped app diverged slightly.*

## Context

You have two boys whose fully-built Lego sets eventually get disassembled and mixed into one giant bin of loose pieces. Rebuilding an old set is hard because the instruction booklet and the set number are long gone. The goal is a Streamlit app, "BrickBot," that lets a child browse Lego sets visually (by theme, without needing to know a set number) and then see exactly which parts, colors, quantities, and minifigures are needed to rebuild that specific set — with pictures, since a 2025 kid can't read a part number but can absolutely recognize a picture.

This plan covers the data model, cleaning rules, loading/performance strategy, and screen-by-screen UX design, using the Kaggle "Lego Database 2025" CSVs already downloaded to `BrickBot/Data`.

## 1. Data inventory (verified against actual files, not the ERD image)

The `Lego Data Model.png` ERD in the Data folder shows some tables (`elements`, `part_categories`, `part_relationships`) that **do not exist** in this particular download — only 8 CSVs are present. The plan below is based on the real files:

| File | Rows | Size | Key columns |
|---|---|---|---|
| `themes.csv` | 482 | 10 KB | `id` (PK), `name`, `parent_id` (FK → themes.id, self-referencing) |
| `sets.csv` | 25,635 | 2.4 MB | `set_num` (PK), `name`, `year`, `theme_id` (FK → themes.id), `num_parts`, `img_url` |
| `inventories.csv` | 43,622 | 815 KB | `id` (PK), `version`, `set_num` (FK → sets.set_num) |
| `inventory_parts.csv` | 1,429,610 | **122 MB** | `inventory_id` (FK → inventories.id), `part_num` (FK → parts.part_num), `color_id` (FK → colors.id), `quantity`, `is_spare`, `img_url` |
| `inventory_minifigs.csv` | 24,305 | 486 KB | `inventory_id` (FK → inventories.id), `fig_num` (FK → minifigs.fig_num), `quantity` |
| `parts.csv` | 59,806 | 5.3 MB | `part_num` (PK), `name`, `part_cat_id`, `part_material` |
| `minifigs.csv` | 16,132 | 1.8 MB | `fig_num` (PK), `name`, `num_parts`, `img_url` |
| `colors.csv` | 274 | 14 KB | `id` (PK), `name`, `rgb` (hex, no `#`), `is_trans`, `num_parts`, `num_sets` |

Notable real-world quirks discovered while inspecting structure/samples:
- **Theme hierarchy is up to 3 levels deep** in places (e.g. a theme can have a parent which itself has a parent). 148 of 482 themes are top-level (`parent_id` empty).
- **`parts.csv` has no image column.** Part images only exist per (part, color) combination inside `inventory_parts.img_url`. This is actually convenient since we need the part-in-the-right-color image anyway.
- **~3% of sets (1,218 of 41,765) have more than one `inventories` row** (multiple `version`s for the same `set_num`) — need a tie-breaker rule (see §3).
- `set_num` values already carry their variant suffix (e.g. `7922-1`) and match 1:1 between `sets.csv` and `inventories.csv`.

## 2. Join path (data model)

```
themes (self-join on parent_id, up to 3 levels)
   │  id ──────────────► sets.theme_id
   ▼
 sets  (set_num) ──────────────► inventories.set_num
                                      │ id
                    ┌─────────────────┴──────────────────┐
                    ▼                                     ▼
        inventory_parts.inventory_id           inventory_minifigs.inventory_id
              │ part_num, color_id                        │ fig_num
              ▼                                            ▼
        parts.part_num  +  colors.id                 minifigs.fig_num
```

- **Screen 1** walks: `themes` → `themes` (subtheme) → `sets`.
- **Screen 2** walks: `sets.set_num` → `inventories` (pick one version) → `inventory_parts` + `inventory_minifigs` → enrich with `parts`, `colors`, `minifigs`.

## 3. Data cleaning rules

Per project instructions, low emphasis on data quality — just skip broken rows, no repair/imputation:

- **Drop any row with a null/blank value in a primary-key or foreign-key column** before it's used for joins: e.g. `sets` rows with blank `theme_id`, `inventory_parts` rows with blank `part_num`/`color_id`/`inventory_id`, etc. This happens once at load time via `dropna(subset=[...])` on the relevant key columns per table.
- **Non-key nulls are kept**, e.g. blank `img_url` — Screen 1/2 render a placeholder brick icon instead of dropping the set/part.
- **Multiple inventory versions per set** (the ~3% case): take the row with **`max(version)`** for that `set_num`. This is a reasonable, unambiguous tie-breaker and matches Rebrickable convention that higher version = latest corrected inventory.
- **Spare parts**: `inventory_parts.is_spare == True` rows are extra/replacement pieces, not part of the "must find to rebuild" count. The main build list (`is_spare == False`) is shown by default, with spares in a small collapsed "extra spare pieces" section underneath rather than mixed in — avoids a confused kid thinking they're missing a piece that was actually just a spare.

## 4. Data loading & performance strategy

Approach: **pandas + Streamlit caching**, all in-memory, no DB/ETL step.

- `themes.csv`, `sets.csv`, `colors.csv`, `parts.csv`, `minifigs.csv`, `inventories.csv` are small (≤5MB) — loaded fully as pandas DataFrames.
- `inventory_parts.csv` (122MB / 1.4M rows) is the one to watch, but with only 5 narrow columns it's ~250–350MB as a DataFrame, which is fine to hold in memory for a local personal app.
- Every load function wrapped in `@st.cache_data` so the CSVs are parsed **once per app process**, not on every rerun/click.
- Loaded once at app startup into a `data.py` module with functions like `load_themes()`, `load_sets()`, `load_inventory_parts()`, etc., each doing the read + key-null-drop in one place.
- If this ever feels slow in practice, the fallback is switching `inventory_parts` access to DuckDB queried directly against the CSV (no rewrite of the UI layer needed, just the data-access functions) — noted here but not needed at this data size.

## 5. Screen 1 — Browse & Pick a Set

**Flow:** Theme dropdown → Subtheme dropdown → grid of matching sets as image cards.

- Theme dropdown: `themes` where `parent_id` is blank, sorted alphabetically.
- Subtheme dropdown: `themes` where `parent_id == selected theme id`, with an **"All"** option so kids can see everything under a theme without picking a subtheme.
- **3rd-level rollup:** if a chosen subtheme itself has children (3rd-level themes), sets are gathered from that subtheme **and all of its descendant themes** — no 3rd dropdown, keeping the UI to exactly 2 pickers.
- Set list: `sets` filtered by resolved theme id(s), rendered as a responsive card grid — each card: `img_url` (placeholder brick icon if blank), set name, year, piece count, and an explicit bright **"Build this set!"** button to select it (added per review feedback — see notes below).
- Clicking the button stores `st.session_state.selected_set_num` and switches to Screen 2.

## 6. Screen 2 — What You Need to Rebuild It

**Flow:** header showing the chosen set (image, name, year) + a "← Back to sets" button, then Minifigures and Parts sections.

- Resolve `inventory_id` for the selected `set_num` (max version rule from §3).
- **Parts section:** join `inventory_parts` (spares excluded) → `parts` (name) → `colors` (name + `rgb` hex for a color swatch). Card grid: part image, part name, color swatch + name, quantity. Sorted by quantity descending so the most-needed pieces catch the eye first.
- **Spare parts:** same layout, in a collapsed expander beneath the main grid.
- **Minifigures section:** join `inventory_minifigs` → `minifigs` (name, `img_url`, quantity), same card-grid treatment.
- All grids use the same fixed-size image container + consistent card height so rows align regardless of varying name/color-name lengths.

## 7. Visual design (colorful, playful, modern)

- **Font:** Google Font **"Baloo 2"** for headings/buttons (rounded, chunky, playful) paired with **"Nunito"** for body text.
- **Palette:** bright primary Lego-brick colors (red `#D62E2E`, yellow `#F5C518`, blue `#0055BF`, green `#237841`) as accents on a clean white/light background.
- **Cards & alignment:** rounded, bordered cards with fixed-height containers so grids stay tidy regardless of varying image aspect ratios or text length.

## 8. Navigation / state

- Two-screen navigation handled via `st.session_state` (`screen`: `"browse"` | `"build"`, plus `selected_set_num`) — no multipage app structure needed for just 2 screens.

## 9. Proposed app structure

```
BrickBot/
  app.py          # Streamlit entrypoint, screen router, UI
  data.py         # cached CSV loaders + key-null cleaning + join helpers
  Data/           # existing Kaggle CSVs (unchanged)
```

## 10. Verification plan

- Run the app locally (`streamlit run app.py`), confirm cold-start load time is acceptable.
- Spot-check a top-level theme with no subthemes, one with subthemes, and one with 3-level depth (to confirm rollup works).
- Spot-check a set that has multiple inventory versions to confirm the max-version pick looks correct.
- Spot-check a set with zero minifigs and one with several, and a set with spare parts, to confirm sections hide/collapse gracefully.
- Confirm broken/missing `img_url` values fall back to a placeholder rather than a broken-image icon.

---

## Implementation notes (where the shipped app diverged from this plan)

- **Theming:** instead of hand-rolled CSS for fonts/cards/colors (§7), the fonts and color palette were applied natively via `.streamlit/config.toml` (Streamlit's built-in theming system), which achieves the same colorful/playful/modern look with less custom code to maintain.
- **File structure:** no separate `ui_components.py` was needed — card rendering and image-placeholder helpers live directly in `app.py` alongside the two screens, since the app stayed small.
- **Screen 1 additions beyond the plan:** a search-by-name box and page-based pagination (12 sets/page) were added once it became clear some themes have hundreds of sets — not in the original plan but a natural extension of it.
- **Select button:** the plan's clickable card was made into an explicit, clearly labeled "🧱 Build this set!" button styled in the theme's primary (Lego red) color, per review feedback.
