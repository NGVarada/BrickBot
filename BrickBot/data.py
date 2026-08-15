"""Data loading and lookup helpers for BrickBot.

Loads the Kaggle "Lego Database 2025" CSVs, drops any row with a null
primary/foreign key (per project rules -- data quality isn't a priority
for this fun project, broken rows are just skipped), and exposes small
helper functions that walk the theme -> set -> inventory -> parts/minifigs
join path described in the data model.
"""

from pathlib import Path

import pandas as pd
import streamlit as st

DATA_DIR = Path(__file__).parent / "Data"


# ---------------------------------------------------------------------------
# Cached raw loaders -- each CSV is read once per app process.
# ---------------------------------------------------------------------------


@st.cache_data(show_spinner="Loading themes...")
def load_themes() -> pd.DataFrame:
    df = pd.read_csv(
        DATA_DIR / "themes.csv",
        dtype={"id": "Int64", "name": "string", "parent_id": "Int64"},
    )
    return df.dropna(subset=["id", "name"])


@st.cache_data(show_spinner="Loading sets...")
def load_sets() -> pd.DataFrame:
    df = pd.read_csv(
        DATA_DIR / "sets.csv",
        dtype={
            "set_num": "string",
            "name": "string",
            "year": "Int64",
            "theme_id": "Int64",
            "num_parts": "Int64",
            "img_url": "string",
        },
    )
    df = df.dropna(subset=["set_num", "theme_id"])
    df["name"] = df["name"].fillna(df["set_num"])
    return df


@st.cache_data(show_spinner="Loading set inventories...")
def load_inventories() -> pd.DataFrame:
    df = pd.read_csv(
        DATA_DIR / "inventories.csv",
        dtype={"id": "Int64", "version": "Int64", "set_num": "string"},
    )
    return df.dropna(subset=["id", "set_num"])


@st.cache_data(show_spinner="Loading colors...")
def load_colors() -> pd.DataFrame:
    df = pd.read_csv(
        DATA_DIR / "colors.csv",
        usecols=["id", "name", "rgb", "is_trans"],
        dtype={"id": "Int64", "name": "string", "rgb": "string"},
    )
    df = df.dropna(subset=["id"])
    return df.rename(columns={"name": "color_name"})


@st.cache_data(show_spinner="Loading parts catalog...")
def load_parts() -> pd.DataFrame:
    df = pd.read_csv(
        DATA_DIR / "parts.csv",
        usecols=["part_num", "name"],
        dtype={"part_num": "string", "name": "string"},
    )
    df = df.dropna(subset=["part_num"])
    return df.rename(columns={"name": "part_name"})


@st.cache_data(show_spinner="Loading minifigures...")
def load_minifigs() -> pd.DataFrame:
    df = pd.read_csv(
        DATA_DIR / "minifigs.csv",
        dtype={
            "fig_num": "string",
            "name": "string",
            "num_parts": "Int64",
            "img_url": "string",
        },
    )
    return df.dropna(subset=["fig_num"])


@st.cache_data(show_spinner="Loading all the Lego pieces (this can take a moment)...")
def load_inventory_parts() -> pd.DataFrame:
    df = pd.read_csv(
        DATA_DIR / "inventory_parts.csv",
        dtype={
            "inventory_id": "Int64",
            "part_num": "string",
            "color_id": "Int64",
            "quantity": "Int64",
            "is_spare": "boolean",
            "img_url": "string",
        },
    )
    return df.dropna(subset=["inventory_id", "part_num", "color_id"])


@st.cache_data(show_spinner="Loading minifigure lists...")
def load_inventory_minifigs() -> pd.DataFrame:
    df = pd.read_csv(
        DATA_DIR / "inventory_minifigs.csv",
        dtype={"inventory_id": "Int64", "fig_num": "string", "quantity": "Int64"},
    )
    return df.dropna(subset=["inventory_id", "fig_num"])


# ---------------------------------------------------------------------------
# Theme hierarchy helpers
# ---------------------------------------------------------------------------


def get_top_level_themes(themes: pd.DataFrame) -> pd.DataFrame:
    return themes[themes["parent_id"].isna()].sort_values("name")


def get_subthemes(themes: pd.DataFrame, theme_id: int) -> pd.DataFrame:
    return themes[themes["parent_id"] == theme_id].sort_values("name")


def get_descendant_theme_ids(themes: pd.DataFrame, theme_id: int) -> list[int]:
    """Theme id plus every theme nested under it, at any depth."""
    ids = [theme_id]
    for child_id in themes.loc[themes["parent_id"] == theme_id, "id"].tolist():
        ids.extend(get_descendant_theme_ids(themes, child_id))
    return ids


# ---------------------------------------------------------------------------
# Set / inventory helpers
# ---------------------------------------------------------------------------


def get_sets_for_theme(sets_df: pd.DataFrame, theme_ids: list[int]) -> pd.DataFrame:
    return sets_df[sets_df["theme_id"].isin(theme_ids)].sort_values("name")


def get_best_inventory_id(inventories: pd.DataFrame, set_num: str) -> int | None:
    """Pick the highest-version inventory for a set (handles the ~3% of
    sets that have more than one inventory revision)."""
    matches = inventories[inventories["set_num"] == set_num]
    if matches.empty:
        return None
    return int(matches.loc[matches["version"].idxmax(), "id"])


def get_parts_for_inventory(
    inventory_parts: pd.DataFrame,
    parts: pd.DataFrame,
    colors: pd.DataFrame,
    inventory_id: int,
    is_spare: bool = False,
) -> pd.DataFrame:
    subset = inventory_parts[
        (inventory_parts["inventory_id"] == inventory_id)
        & (inventory_parts["is_spare"].fillna(False) == is_spare)
    ]
    merged = subset.merge(parts, on="part_num", how="left")
    merged = merged.merge(colors, left_on="color_id", right_on="id", how="left")
    merged["part_name"] = merged["part_name"].fillna(merged["part_num"])
    merged["color_name"] = merged["color_name"].fillna("Unknown color")
    merged["rgb"] = merged["rgb"].fillna("CCCCCC")
    merged["quantity"] = merged["quantity"].fillna(0).astype("int64")
    return merged.sort_values("quantity", ascending=False)


def get_minifigs_for_inventory(
    inventory_minifigs: pd.DataFrame,
    minifigs: pd.DataFrame,
    inventory_id: int,
) -> pd.DataFrame:
    subset = inventory_minifigs[inventory_minifigs["inventory_id"] == inventory_id]
    merged = subset.merge(minifigs, on="fig_num", how="left")
    merged["name"] = merged["name"].fillna(merged["fig_num"])
    merged["quantity"] = merged["quantity"].fillna(0).astype("int64")
    return merged.sort_values("quantity", ascending=False)
