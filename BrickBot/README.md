# 🧱 BrickBot

A colorful, kid-friendly Streamlit app for finding a Lego set by picture and seeing exactly which parts, colors, quantities, and minifigures are needed to rebuild it.

## Problem it solves

Fully built Lego sets are hard to store, and once they get taken apart the pieces end up mixed into one big bin with everything else. Rebuilding an old set later is difficult because the instruction booklet and the set number are usually long gone. BrickBot lets a kid browse sets visually by theme — no set number or reading required — then shows a picture-based checklist of every part, color, quantity, and minifigure needed to put that set back together.

## Features

**Screen 1 — Browse & pick a set**
- Pick a Theme, then a Subtheme (sets from nested sub-subthemes are automatically rolled in)
- Search sets by name
- Paginated grid of set cards with photo, name, year, and piece count
- A bright "🧱 Build this set!" button on each card to select it

**Screen 2 — What you need to rebuild it**
- Set header with photo, name, year, and total piece count
- Minifigures needed, with photo and quantity
- Parts needed, with photo, part name, color swatch + color name, and quantity (sorted by quantity, most-needed first)
- Spare pieces tucked into a collapsible section so they don't get confused with required parts

## Data

Built on the [Lego Database 2025](https://www.kaggle.com/datasets/iamjcmc/lego-database-2025) Kaggle dataset. The CSVs live in `Data/` and are not included in this repo listing here — download them from Kaggle and place them in `BrickBot/Data/` with these files:

```
Data/
  themes.csv
  sets.csv
  inventories.csv
  inventory_parts.csv
  inventory_minifigs.csv
  parts.csv
  minifigs.csv
  colors.csv
```

Any row missing a primary or foreign key value is skipped when the app loads (this project doesn't try to repair or impute broken source data — see [PLAN.md](PLAN.md) for details on the data model, join paths, and cleaning rules).

## Setup

```bash
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

Then open the URL Streamlit prints (defaults to http://localhost:8501).

## Project structure

```
BrickBot/
  app.py                  # Streamlit entrypoint — both screens, card rendering
  data.py                 # Cached CSV loaders, null-key cleaning, join/lookup helpers
  .streamlit/config.toml  # Colorful theme (Baloo 2 / Nunito fonts, Lego-brick palette)
  Data/                   # Kaggle CSVs (download separately, see above)
  PLAN.md                 # Design plan reviewed before building the app
```

## Notes

- All data is loaded into memory once per app process (via `st.cache_data`) — no database or ETL step required.
- When a set has multiple inventory revisions, the highest version number is used.
- Missing images fall back to a placeholder brick icon rather than a broken image.
