import pandas as pd
import streamlit as st

import data

st.set_page_config(page_title="BrickBot", page_icon="🧱", layout="wide")

themes = data.load_themes()
sets_df = data.load_sets()
inventories = data.load_inventories()
colors = data.load_colors()
parts = data.load_parts()
minifigs = data.load_minifigs()

if "screen" not in st.session_state:
    st.session_state.screen = "browse"
if "selected_set_num" not in st.session_state:
    st.session_state.selected_set_num = None


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def render_image(img_url, height=170, emoji="🧱"):
    has_img = isinstance(img_url, str) and img_url.strip() != ""
    with st.container(
        height=height,
        horizontal_alignment="center",
        vertical_alignment="center",
        gap=None,
        border=not has_img,
    ):
        if has_img:
            st.image(img_url, width="stretch")
        else:
            st.markdown(f"## {emoji}")
            st.caption("No photo yet")


def render_card_grid(df, card_fn, cols_per_row=4):
    records = df.to_dict("records")
    for i in range(0, len(records), cols_per_row):
        row_items = records[i : i + cols_per_row]
        cols = st.columns(cols_per_row)
        for col, item in zip(cols, row_items):
            with col:
                card_fn(item)


# ---------------------------------------------------------------------------
# Screen 1 — Browse & pick a set
# ---------------------------------------------------------------------------


def set_card(row):
    with st.container(border=True, height=440):
        render_image(row["img_url"], height=190)
        name = row["name"] if len(row["name"]) <= 55 else row["name"][:52] + "..."
        st.markdown(f"**{name}**")
        year = "" if pd.isna(row["year"]) else str(int(row["year"]))
        num_parts = "" if pd.isna(row["num_parts"]) else f"{int(row['num_parts'])} pieces"
        st.caption(" • ".join(x for x in [year, num_parts] if x))
        if st.button(
            "🧱 Build this set!",
            key=f"pick_set_{row['set_num']}",
            type="primary",
            width="stretch",
        ):
            st.session_state.selected_set_num = row["set_num"]
            st.session_state.screen = "build"
            st.rerun()


def browse_screen():
    st.title("🧱 BrickBot")
    st.caption("Pick a theme, find your set, and see exactly what pieces you need to rebuild it!")

    top_themes = data.get_top_level_themes(themes)

    theme_col, sub_col, search_col = st.columns([1, 1, 1.4])
    with theme_col:
        selected_theme_name = st.selectbox("Theme", top_themes["name"].tolist(), key="theme_select")
    selected_theme_id = int(top_themes.loc[top_themes["name"] == selected_theme_name, "id"].iloc[0])

    subthemes = data.get_subthemes(themes, selected_theme_id)
    with sub_col:
        sub_options = ["All"] + subthemes["name"].tolist()
        selected_sub_name = st.selectbox(
            "Subtheme", sub_options, key=f"sub_select_{selected_theme_id}"
        )

    if selected_sub_name == "All":
        theme_ids = data.get_descendant_theme_ids(themes, selected_theme_id)
    else:
        sub_id = int(subthemes.loc[subthemes["name"] == selected_sub_name, "id"].iloc[0])
        theme_ids = data.get_descendant_theme_ids(themes, sub_id)

    matched_sets = data.get_sets_for_theme(sets_df, theme_ids)

    with search_col:
        search = st.text_input(
            "Search set name", key="set_search", placeholder="Search by set name..."
        )
    if search:
        matched_sets = matched_sets[
            matched_sets["name"].str.contains(search, case=False, na=False, regex=False)
        ]

    st.caption(f"🔎 {len(matched_sets)} set(s) found")

    if matched_sets.empty:
        st.info("No sets found — try a different theme or search term.")
        return

    page_size = 12
    num_pages = max(1, -(-len(matched_sets) // page_size))
    with st.container(horizontal_alignment="right"):
        page = st.pagination(
            num_pages, key=f"sets_page_{selected_theme_id}_{selected_sub_name}_{search}"
        )
    start = (page - 1) * page_size
    render_card_grid(matched_sets.iloc[start : start + page_size], set_card, cols_per_row=4)


# ---------------------------------------------------------------------------
# Screen 2 — What you need to rebuild it
# ---------------------------------------------------------------------------


def part_card(row):
    with st.container(border=True, height=310):
        render_image(row["img_url"], height=140, emoji="🔩")
        part_name = row["part_name"]
        part_name = part_name if len(part_name) <= 45 else part_name[:42] + "..."
        st.markdown(f"**{part_name}**")
        swatch_col, name_col = st.columns([1, 4], vertical_alignment="center")
        with swatch_col:
            st.color_picker(
                "Color",
                value=f"#{row['rgb']}",
                key=f"swatch_{row['inventory_id']}_{row['part_num']}_{row['color_id']}_{row['is_spare']}",
                disabled=True,
                label_visibility="collapsed",
            )
        with name_col:
            st.caption(row["color_name"])
        st.markdown(f"Need: **× {row['quantity']}**")


def minifig_card(row):
    with st.container(border=True, height=300):
        render_image(row["img_url"], height=170, emoji="🧑‍🚀")
        st.markdown(f"**{row['name']}**")
        st.markdown(f"Need: **× {row['quantity']}**")


def build_screen():
    set_num = st.session_state.selected_set_num
    match = sets_df.loc[sets_df["set_num"] == set_num]

    if st.button("← Back to sets", icon=":material/arrow_back:"):
        st.session_state.screen = "browse"
        st.rerun()

    if match.empty:
        st.warning("That set couldn't be found. Please go back and pick another one.")
        return
    set_row = match.iloc[0]

    header_img_col, header_info_col = st.columns([1, 2], vertical_alignment="center")
    with header_img_col:
        render_image(set_row["img_url"], height=220)
    with header_info_col:
        st.header(set_row["name"])
        year = "" if pd.isna(set_row["year"]) else str(int(set_row["year"]))
        num_parts = (
            "" if pd.isna(set_row["num_parts"]) else f"{int(set_row['num_parts'])} total pieces"
        )
        st.caption(" • ".join(x for x in [f"Set #{set_num}", year, num_parts] if x))

    inventory_id = data.get_best_inventory_id(inventories, set_num)
    if inventory_id is None:
        st.warning("We don't have a parts list for this set yet.")
        return

    inventory_parts = data.load_inventory_parts()
    inventory_minifigs = data.load_inventory_minifigs()

    minifig_df = data.get_minifigs_for_inventory(inventory_minifigs, minifigs, inventory_id)
    if not minifig_df.empty:
        st.subheader(f"🧑‍🚀 Minifigures ({int(minifig_df['quantity'].sum())})")
        render_card_grid(minifig_df, minifig_card, cols_per_row=5)

    part_df = data.get_parts_for_inventory(inventory_parts, parts, colors, inventory_id, is_spare=False)
    total_parts = int(part_df["quantity"].sum()) if not part_df.empty else 0
    st.subheader(f"🔧 Parts you'll need ({total_parts})")
    if part_df.empty:
        st.info("No parts found for this set.")
    else:
        render_card_grid(part_df, part_card, cols_per_row=4)

    spare_df = data.get_parts_for_inventory(inventory_parts, parts, colors, inventory_id, is_spare=True)
    if not spare_df.empty:
        with st.expander(f"🧰 Extra spare pieces ({int(spare_df['quantity'].sum())})"):
            render_card_grid(spare_df, part_card, cols_per_row=4)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

if st.session_state.screen == "browse":
    browse_screen()
else:
    build_screen()
