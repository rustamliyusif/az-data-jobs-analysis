import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from features import SKILLS

HISTORY_PATH = ROOT / "data" / "processed" / "vacancies_history.csv"
SKILL_COLUMNS = list(SKILLS)
LANGUAGES = ["English", "Russian"]
SENIORITY_ORDER = ["Intern", "Junior / Mid", "Senior", "Lead / Head"]
BLUE = "#2a78d6"

st.set_page_config(page_title="AZ IT Jobs", page_icon="📊", layout="wide")


@st.cache_data(ttl=3600)
def load() -> pd.DataFrame:
    df = pd.read_csv(HISTORY_PATH, dtype={"first_seen": str, "last_seen": str})
    for column in SKILL_COLUMNS:
        df[column] = df[column].fillna(False).astype(bool) if column in df else False
    df["first_seen"] = pd.to_datetime(df["first_seen"])
    df["last_seen"] = pd.to_datetime(df["last_seen"])
    df["url"] = "https://www.hellojob.az/vakansiya/" + df["id"]
    return df


def bar(series: pd.Series, title: str, suffix: str = "") -> None:
    data = series.sort_values().reset_index()
    data.columns = ["label", "value"]
    fig = px.bar(data, x="value", y="label", orientation="h", text="value", title=title)
    fig.update_traces(marker_color=BLUE, texttemplate="%{text}" + suffix, textposition="outside", cliponaxis=False)
    fig.update_layout(xaxis_title=None, yaxis_title=None, height=90 + 32 * len(data),
                      margin=dict(l=0, r=40, t=50, b=0), xaxis=dict(showticklabels=False, showgrid=False))
    st.plotly_chart(fig, width="stretch")


df = load()
latest = df["last_seen"].max()

st.title("Azərbaycanda IT vakansiyaları nə tələb edir?")
st.caption(f"Mənbə: hellojob.az · son yenilənmə: {latest:%d.%m.%Y} · hər gün avtomatik yenilənir")

with st.sidebar:
    st.header("Filtrlər")
    only_active = st.toggle("Yalnız aktiv vakansiyalar", value=True)
    families = st.multiselect("Rol", sorted(df["role_family"].dropna().unique()), placeholder="Hamısı")
    levels = st.multiselect("Səviyyə", [s for s in SENIORITY_ORDER if s in set(df["seniority"])], placeholder="Hamısı")

view = df[df["last_seen"] == latest] if only_active else df
if families:
    view = view[view["role_family"].isin(families)]
if levels:
    view = view[view["seniority"].isin(levels)]

if view.empty:
    st.warning("Seçilmiş filtrlərə uyğun vakansiya yoxdur.")
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Vakansiya", len(view))
c2.metric("Şirkət", view["company"].nunique())
median_exp = view["min_experience_years"].median()
c3.metric("Minimum təcrübə (median)", f"{median_exp:.0f} il" if pd.notna(median_exp) else "—")
c4.metric("Maaşı göstərilən", f"{view['salary_disclosed'].mean() * 100:.0f}%")

tab_skills, tab_market, tab_match, tab_trend = st.tabs(
    ["Bacarıqlar", "Şirkətlər və səviyyə", "Mənə uyğun vakansiyalar", "Trend"])

with tab_skills:
    share = (view[SKILL_COLUMNS].mean() * 100).round(0)
    left, right = st.columns(2)
    with left:
        tech = share.drop(LANGUAGES, errors="ignore")
        bar(tech[tech > 0].sort_values(ascending=False).head(20), "Ən çox tələb olunan 20 bacarıq (% vakansiya)", "%")
    with right:
        bar(share.reindex(LANGUAGES).fillna(0), "Dil tələbləri (% vakansiya)", "%")
    top_roles = view["role_family"].value_counts().head(10).index
    tech_columns = [c for c in SKILL_COLUMNS if c not in LANGUAGES]
    top_skills = view[tech_columns].mean().sort_values(ascending=False).head(15).index
    by_role = view[view["role_family"].isin(top_roles)].groupby("role_family")[list(top_skills)].mean().mul(100).round(0)
    if len(by_role) > 1:
        fig = px.imshow(by_role, text_auto=True, aspect="auto", color_continuous_scale="Blues",
                        title="Rol üzrə bacarıqlar (%)")
        fig.update_layout(coloraxis_showscale=False, xaxis_title=None, yaxis_title=None,
                          height=120 + 60 * len(by_role), margin=dict(l=0, r=0, t=50, b=0))
        fig.update_xaxes(side="top")
        st.plotly_chart(fig, width="stretch")

with tab_market:
    left, right = st.columns(2)
    with left:
        bar(view["company"].value_counts().head(15), "Ən çox işə götürən şirkətlər")
    with right:
        bar(view["seniority"].value_counts().reindex(SENIORITY_ORDER).dropna().astype(int)[::-1],
            "Səviyyə üzrə bölgü")
        bar(view["role_family"].value_counts(), "Rol üzrə bölgü")

with tab_match:
    mine = st.multiselect("Bildiyin bacarıqları seç", SKILL_COLUMNS, default=["SQL", "Python"], placeholder="Bacarıq seç")
    required = view[SKILL_COLUMNS]
    needed = required.sum(axis=1)
    have = required[mine].sum(axis=1) if mine else 0
    matches = view.assign(
        uyğunluq=(have / needed.where(needed > 0)).mul(100).round(0),
        çatışmayan=required.apply(lambda row: ", ".join(s for s in SKILL_COLUMNS if row[s] and s not in mine), axis=1),
    ).sort_values(["uyğunluq", "min_experience_years"], ascending=[False, True])
    st.dataframe(
        matches[["title", "company", "seniority", "min_experience_years", "uyğunluq", "çatışmayan", "url"]],
        column_config={
            "title": "Vəzifə", "company": "Şirkət", "seniority": "Səviyyə",
            "min_experience_years": st.column_config.NumberColumn("Təcrübə (il)", format="%d"),
            "uyğunluq": st.column_config.ProgressColumn("Uyğunluq", format="%d%%", min_value=0, max_value=100),
            "çatışmayan": "Çatışmayan bacarıqlar",
            "url": st.column_config.LinkColumn("Link", display_text="Aç"),
        },
        hide_index=True, width="stretch",
    )

with tab_trend:
    snapshots = df["last_seen"].nunique()
    if snapshots < 3:
        st.info("Trend qrafikləri üçün ən azı bir neçə günlük data lazımdır. Data hər gün avtomatik yığılır.")
    weekly = view.set_index("first_seen").resample("W")["id"].count().rename("Yeni vakansiya")
    fig = px.bar(weekly.reset_index(), x="first_seen", y="Yeni vakansiya", title="Həftəlik yeni vakansiyalar")
    fig.update_traces(marker_color=BLUE)
    fig.update_layout(xaxis_title=None, margin=dict(l=0, r=0, t=50, b=0))
    st.plotly_chart(fig, width="stretch")

st.divider()
st.caption("Müəllif: Yusif Rustamli · "
           "[GitHub](https://github.com/rustamliyusif/az-data-jobs-analysis) · "
           "Bacarıqlar vakansiya mətnindən açar söz üzrə aşkarlanır, nəticələr təxminidir.")
