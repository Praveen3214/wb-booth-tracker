"""
West Bengal Focused Booth Tracker Dashboard
============================================
Interactive Streamlit dashboard with cascading dropdowns,
KPI cards, and charts. Pulls live data from Google Sheets.

Usage:
    pip install -r requirements_dashboard.txt
    streamlit run dashboard.py
"""

import io

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

# --------------- Configuration ---------------

SHEET_ID = "1ZI_orys8bZWcBL19v2JjdLNapuMphJDqyO6dNm5EfPM"
SHEET_NAME = "Rough_Booth wise"
CSV_URL = (
    f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
    f"/gviz/tq?tqx=out:csv&sheet={SHEET_NAME.replace(' ', '%20')}"
)

# The Google Sheet has a 2-row header: row 1 is grouping labels (1,2,3...8),
# row 2 has some named columns but many are "Unnamed".
# After reading with header=1, we rename by position.

# Positional column mapping (0-indexed after header=1)
# These map the Unnamed columns to meaningful names.
POS_RENAME = {
    0: "Key_Booth",
    1: "Key_AC",
    2: "Coordinator",
    3: "Zone",
    4: "AC No",
    5: "AC Name",
    6: "Booth Number",
    7: "Booth Name",
    8: "Verified BJP Supporter",
    9: "BP Appointed",
    10: "BP Verified",
    11: "Secretary Appointed",
    12: "Secretary Verified",
    13: "BLA-2 Appointed",
    14: "BLA-2 Verified",
    15: "BK Expected",
    16: "BK Verified",
    17: "Primary Members",
    18: "Women FD Count",
    19: "Women FD Benefitted",
    20: "Other FD Count",
    21: "Other FD Benefitted",
    22: "Calling BJP Supporter",
    23: "Active Karyakarta",
    24: "Dark",
    25: "Bronze",
    26: "Silver",
    27: "Gold",
    28: "Platinum",
    29: "Ekal",
    30: "Gaudiya",
    31: "Vichar Parivar Leader",
    32: "Impactful INC Leader",
    33: "Impactful Left Leader",
    34: "Final Sum",
}

NUMERIC_COLS = [
    "Verified BJP Supporter", "BP Appointed", "BP Verified",
    "Secretary Appointed", "Secretary Verified",
    "BLA-2 Appointed", "BLA-2 Verified",
    "BK Expected", "BK Verified",
    "Primary Members",
    "Women FD Count", "Women FD Benefitted",
    "Other FD Count", "Other FD Benefitted",
    "Calling BJP Supporter", "Active Karyakarta",
    "Dark", "Bronze", "Silver", "Gold", "Platinum",
    "Ekal", "Gaudiya", "Vichar Parivar Leader",
    "Impactful INC Leader", "Impactful Left Leader",
    "Final Sum",
]

CATEGORY_COLS = ["Platinum", "Gold", "Silver", "Bronze", "Dark"]
CATEGORY_COLORS = {
    "Platinum": "#E5E4E2",
    "Gold": "#FFD700",
    "Silver": "#C0C0C0",
    "Bronze": "#CD7F32",
    "Dark": "#2C2C2C",
}


# --------------- Data Loading ---------------

def parse_indian_number(val):
    """Parse Indian-format numbers like '10,45,121' or ' 10,45,121'."""
    if pd.isna(val):
        return 0
    s = str(val).strip()
    if not s or s == "-":
        return 0
    s = s.replace(",", "").replace(" ", "")
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return 0


@st.cache_data(ttl=300, show_spinner="Fetching live data from Google Sheets...")
def load_data():
    """Load data from Google Sheets CSV export."""
    try:
        resp = requests.get(CSV_URL, timeout=60)
        resp.raise_for_status()
        # header=1 skips the grouping row (row 1) and uses row 2 as headers
        df = pd.read_csv(io.StringIO(resp.text), dtype=str, header=1)
    except Exception as e:
        st.warning(f"Could not fetch live data: {e}. Trying local fallback...")
        try:
            df = pd.read_csv("data/booth_data.csv", dtype=str, header=1)
        except FileNotFoundError:
            st.error("No data source available. Place booth_data.csv in data/ folder.")
            return pd.DataFrame()

    # Rename columns by position (first 35 columns are the data we need)
    old_cols = list(df.columns)
    new_names = {}
    for pos, name in POS_RENAME.items():
        if pos < len(old_cols):
            new_names[old_cols[pos]] = name
    df = df.rename(columns=new_names)

    # Keep only the columns we care about
    keep_cols = [c for c in POS_RENAME.values() if c in df.columns]
    df = df[keep_cols].copy()

    # Drop the summary row (first data row where Key_Booth is "-")
    if len(df) > 0 and str(df.iloc[0].get("Key_Booth", "")).strip() == "-":
        df = df.iloc[1:].reset_index(drop=True)

    # Drop rows where Zone or AC Name is missing/dash/empty
    df = df[
        df["Zone"].notna()
        & (df["Zone"].str.strip() != "")
        & (df["Zone"].str.strip() != "-")
    ].reset_index(drop=True)

    # Parse numeric columns
    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = df[col].apply(parse_indian_number)

    # Parse AC No and Booth Number
    if "AC No" in df.columns:
        df["AC No"] = pd.to_numeric(df["AC No"], errors="coerce").fillna(0).astype(int)
    if "Booth Number" in df.columns:
        df["Booth Number"] = pd.to_numeric(df["Booth Number"], errors="coerce").fillna(0).astype(int)

    # Derive booth category from binary flags
    def get_category(row):
        for cat in CATEGORY_COLS:
            if cat in row and row[cat] == 1:
                return cat
        return "Unknown"

    df["Booth Category"] = df.apply(get_category, axis=1)

    # Also get the Category Status column if we kept extra columns
    # (it's at position 36 in the original sheet)

    return df


# --------------- UI Helpers ---------------

def metric_card(label, value, total=None):
    """Render a styled metric card with optional progress bar."""
    if total is not None and total > 0:
        pct = value / total * 100
        pct_str = f"{pct:.0f}%"
        bar_color = "#4CAF50" if pct >= 70 else "#FF9800" if pct >= 40 else "#F44336"
        st.markdown(f"""
        <div style="background: #1A1D23; border-radius: 10px; padding: 16px; border: 1px solid #333;">
            <div style="color: #888; font-size: 13px; margin-bottom: 4px;">{label}</div>
            <div style="font-size: 22px; font-weight: 700; color: #FFF;">
                {value:,} <span style="font-size: 13px; color: #888;">/ {total:,}</span>
            </div>
            <div style="background: #333; border-radius: 4px; height: 6px; margin-top: 8px;">
                <div style="background: {bar_color}; width: {min(pct, 100):.0f}%; height: 6px; border-radius: 4px;"></div>
            </div>
            <div style="color: {bar_color}; font-size: 13px; margin-top: 4px; font-weight: 600;">{pct_str}</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="background: #1A1D23; border-radius: 10px; padding: 16px; border: 1px solid #333;">
            <div style="color: #888; font-size: 13px; margin-bottom: 4px;">{label}</div>
            <div style="font-size: 22px; font-weight: 700; color: #FFF;">{value:,}</div>
        </div>
        """, unsafe_allow_html=True)


def summary_metric(label, value, total=None):
    """Small summary metric for the top bar."""
    if total:
        st.markdown(f"""
        <div style="text-align: center;">
            <div style="color: #888; font-size: 12px;">{label}</div>
            <div style="font-size: 20px; font-weight: 700; color: #FFF;">{value} <span style="color: #666; font-size: 14px;">/ {total}</span></div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="text-align: center;">
            <div style="color: #888; font-size: 12px;">{label}</div>
            <div style="font-size: 20px; font-weight: 700; color: #FFF;">{value}</div>
        </div>
        """, unsafe_allow_html=True)


# --------------- Main App ---------------

def main():
    st.set_page_config(
        page_title="WB Booth Tracker",
        page_icon="🗳️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.markdown("""
    <style>
        .block-container { padding-top: 1rem; }
        [data-testid="stSidebar"] { background-color: #0E1117; }
        .stSelectbox label { color: #FAFAFA; font-weight: 600; }
    </style>
    """, unsafe_allow_html=True)

    # Load data
    df = load_data()
    if df.empty:
        st.stop()

    total_booths = len(df)
    total_zones = df["Zone"].nunique()
    total_acs = df["AC Name"].nunique()

    # ---- Sidebar: Cascading Filters ----
    st.sidebar.title("Filters")

    # 1. Zone filter
    zones = sorted(df["Zone"].dropna().unique().tolist())
    selected_zone = st.sidebar.selectbox("Zone", ["All"] + zones)

    if selected_zone != "All":
        zone_filtered = df[df["Zone"] == selected_zone]
    else:
        zone_filtered = df

    # 2. AC filter (cascaded from Zone)
    acs = sorted(zone_filtered["AC Name"].dropna().unique().tolist())
    selected_ac = st.sidebar.selectbox("Vidhan Sabha (AC)", ["All"] + acs)

    if selected_ac != "All":
        ac_filtered = zone_filtered[zone_filtered["AC Name"] == selected_ac]
    else:
        ac_filtered = zone_filtered

    # 3. Booth Category filter (cascaded from AC)
    categories_present = sorted(
        ac_filtered["Booth Category"].dropna().unique().tolist(),
        key=lambda x: CATEGORY_COLS.index(x) if x in CATEGORY_COLS else 99,
    )
    selected_category = st.sidebar.selectbox("Booth Category", ["All"] + categories_present)

    if selected_category != "All":
        filtered = ac_filtered[ac_filtered["Booth Category"] == selected_category]
    else:
        filtered = ac_filtered

    # 4. Booth-level selector (optional, shown only when list is manageable)
    if len(filtered) <= 500 and len(filtered) > 0:
        booth_options = filtered.apply(
            lambda r: f"{r['Booth Number']} - {r.get('Booth Name', '')}", axis=1
        ).tolist()
        selected_booths = st.sidebar.multiselect("Select Booths (optional)", booth_options)
        if selected_booths:
            booth_nums = []
            for b in selected_booths:
                try:
                    booth_nums.append(int(b.split(" - ")[0]))
                except ValueError:
                    pass
            if booth_nums:
                filtered = filtered[filtered["Booth Number"].isin(booth_nums)]

    st.sidebar.markdown("---")
    st.sidebar.caption(f"Showing **{len(filtered):,}** of {total_booths:,} booths")

    if st.sidebar.button("Refresh Data"):
        st.cache_data.clear()
        st.rerun()

    # ---- Header ----
    st.markdown("## West Bengal Focused Booth Tracker")

    # ---- Summary Metrics Row ----
    s1, s2, s3, s4, s5 = st.columns(5)
    with s1:
        summary_metric("Zones", filtered["Zone"].nunique(), total_zones)
    with s2:
        summary_metric("Vidhan Sabhas", filtered["AC Name"].nunique(), total_acs)
    with s3:
        summary_metric("Booths", f"{len(filtered):,}", f"{total_booths:,}")
    with s4:
        summary_metric("Voter Base", f"{filtered['Verified BJP Supporter'].sum():,}")
    with s5:
        summary_metric("Primary Members", f"{filtered['Primary Members'].sum():,}")

    st.markdown("---")

    # ---- Sangathan Appointments KPIs ----
    st.markdown("### Sangathan Appointments")
    c1, c2, c3, c4 = st.columns(4)

    bp_app = filtered["BP Appointed"].sum()
    bp_ver = filtered["BP Verified"].sum()
    sec_app = filtered["Secretary Appointed"].sum()
    sec_ver = filtered["Secretary Verified"].sum()
    bla_app = filtered["BLA-2 Appointed"].sum()
    bla_ver = filtered["BLA-2 Verified"].sum()
    bk_exp = filtered["BK Expected"].sum()
    bk_ver = filtered["BK Verified"].sum()

    with c1:
        metric_card("Booth Pramukh", bp_ver, bp_app)
    with c2:
        metric_card("Secretary", sec_ver, sec_app)
    with c3:
        metric_card("BLA-2", bla_ver, bla_app)
    with c4:
        metric_card("Booth Karyakarta", bk_ver, bk_exp)

    st.markdown("")

    # ---- Charts Row ----
    ch1, ch2 = st.columns(2)

    # Booth Classification Donut
    with ch1:
        st.markdown("### Booth Classification")
        cat_counts = filtered["Booth Category"].value_counts()
        ordered_cats = [c for c in CATEGORY_COLS if c in cat_counts.index]
        if "Unknown" in cat_counts.index:
            ordered_cats.append("Unknown")
        cat_data = cat_counts.reindex(ordered_cats).dropna()

        if not cat_data.empty:
            colors = [CATEGORY_COLORS.get(c, "#666") for c in cat_data.index]
            fig_cat = go.Figure(data=[go.Pie(
                labels=cat_data.index,
                values=cat_data.values,
                hole=0.5,
                marker=dict(colors=colors),
                textinfo="label+value",
                textfont=dict(size=13),
            )])
            fig_cat.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#FAFAFA"),
                showlegend=True,
                legend=dict(font=dict(size=12)),
                height=350,
                margin=dict(t=10, b=10, l=10, r=10),
            )
            st.plotly_chart(fig_cat, use_container_width=True)
        else:
            st.info("No category data available.")

    # Sangathan Completion Bar Chart
    with ch2:
        st.markdown("### Appointment Completion Rate")
        roles = ["Booth Pramukh", "Secretary", "BLA-2", "Booth Karyakarta"]
        verified = [bp_ver, sec_ver, bla_ver, bk_ver]
        appointed = [bp_app, sec_app, bla_app, bk_exp]
        pcts = [v / a * 100 if a > 0 else 0 for v, a in zip(verified, appointed)]

        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            y=roles,
            x=pcts,
            orientation="h",
            marker=dict(
                color=["#4CAF50" if p >= 70 else "#FF9800" if p >= 40 else "#F44336" for p in pcts],
            ),
            text=[f"{p:.0f}%" for p in pcts],
            textposition="auto",
            textfont=dict(size=14, color="#FFF"),
        ))
        fig_bar.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#FAFAFA"),
            xaxis=dict(range=[0, 100], title="Completion %", gridcolor="#333"),
            yaxis=dict(autorange="reversed"),
            height=350,
            margin=dict(t=10, b=40, l=10, r=10),
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    # ---- Women & Other FD Data + Leaders ----
    st.markdown("---")
    d1, d2 = st.columns(2)

    with d1:
        st.markdown("### Field Data")
        women_fd = filtered["Women FD Count"].sum()
        women_ben = filtered["Women FD Benefitted"].sum()
        other_fd = filtered["Other FD Count"].sum()
        other_ben = filtered["Other FD Benefitted"].sum()

        fig_fd = go.Figure()
        fig_fd.add_trace(go.Bar(
            name="Total",
            x=["Women (SHG + Ujjwala)", "Other FD"],
            y=[women_fd, other_fd],
            marker_color="#4A90D9",
        ))
        fig_fd.add_trace(go.Bar(
            name="Benefitted",
            x=["Women (SHG + Ujjwala)", "Other FD"],
            y=[women_ben, other_ben],
            marker_color="#50C878",
        ))
        fig_fd.update_layout(
            barmode="group",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#FAFAFA"),
            yaxis=dict(gridcolor="#333"),
            height=300,
            margin=dict(t=10, b=40, l=10, r=10),
            legend=dict(orientation="h", y=1.1),
        )
        st.plotly_chart(fig_fd, use_container_width=True)

    with d2:
        st.markdown("### Leader Distribution")
        leader_cols = {
            "Ekal": "Ekal",
            "Gaudiya": "Gaudiya",
            "Vichar Parivar": "Vichar Parivar Leader",
            "INC Leader": "Impactful INC Leader",
            "Left Leader": "Impactful Left Leader",
        }
        leader_vals = {}
        for label, col in leader_cols.items():
            if col in filtered.columns:
                leader_vals[label] = filtered[col].sum()

        if leader_vals:
            fig_leader = go.Figure(data=[go.Bar(
                x=list(leader_vals.keys()),
                y=list(leader_vals.values()),
                marker_color=["#FF6B35", "#4A90D9", "#50C878", "#E74C3C", "#9B59B6"],
                text=[f"{v:,}" for v in leader_vals.values()],
                textposition="auto",
                textfont=dict(size=13, color="#FFF"),
            )])
            fig_leader.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#FAFAFA"),
                yaxis=dict(gridcolor="#333"),
                height=300,
                margin=dict(t=10, b=40, l=10, r=10),
            )
            st.plotly_chart(fig_leader, use_container_width=True)

    # ---- AC-level breakdown table ----
    st.markdown("---")
    st.markdown("### AC-wise Summary")

    agg_dict = {
        "Key_Booth": "count",
        "Verified BJP Supporter": "sum",
        "BP Verified": "sum",
        "BP Appointed": "sum",
        "Secretary Verified": "sum",
        "Secretary Appointed": "sum",
        "Primary Members": "sum",
    }
    for cat in CATEGORY_COLS:
        if cat in filtered.columns:
            agg_dict[cat] = "sum"

    ac_summary = filtered.groupby("AC Name").agg(agg_dict).reset_index()
    ac_summary = ac_summary.rename(columns={"Key_Booth": "Booths", "Verified BJP Supporter": "Voters"})

    ac_summary["BP %"] = (
        ac_summary["BP Verified"] / ac_summary["BP Appointed"].replace(0, 1) * 100
    ).round(0).astype(int)
    ac_summary["Sec %"] = (
        ac_summary["Secretary Verified"] / ac_summary["Secretary Appointed"].replace(0, 1) * 100
    ).round(0).astype(int)

    display_cols = ["AC Name", "Booths", "Voters", "BP Verified", "BP %",
                    "Secretary Verified", "Sec %", "Primary Members"]
    for cat in CATEGORY_COLS:
        if cat in ac_summary.columns:
            display_cols.append(cat)

    available_display = [c for c in display_cols if c in ac_summary.columns]
    st.dataframe(
        ac_summary[available_display].sort_values("Booths", ascending=False),
        use_container_width=True,
        height=400,
        hide_index=True,
    )

    # ---- Raw Booth Data (expandable) ----
    with st.expander("View Booth-Level Data", expanded=False):
        display_booth_cols = [
            "AC Name", "Booth Number", "Booth Name", "Booth Category",
            "Verified BJP Supporter", "BP Appointed", "BP Verified",
            "Secretary Appointed", "Secretary Verified",
            "Primary Members", "Women FD Count", "Other FD Count",
        ]
        available_cols = [c for c in display_booth_cols if c in filtered.columns]
        st.dataframe(
            filtered[available_cols].sort_values(["AC Name", "Booth Number"]),
            use_container_width=True,
            height=500,
            hide_index=True,
        )


if __name__ == "__main__":
    main()
