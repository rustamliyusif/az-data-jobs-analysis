import re
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
JUNIOR_TITLE = r"junior|trainee|intern|təcrübəçi|təcrübə proqram|kiçik (?:mütəxəssis|proqramçı|analitik|mühəndis|developer)"
LINK = st.column_config.LinkColumn("Link", display_text="Aç")

st.set_page_config(page_title="AZ IT Jobs", page_icon="📊", layout="wide")


@st.cache_data
def load(version: float) -> pd.DataFrame:
    df = pd.read_csv(HISTORY_PATH, dtype={"first_seen": str, "last_seen": str})
    for column in SKILL_COLUMNS:
        df[column] = df[column].fillna(False).astype(bool) if column in df else False
    df["first_seen"] = pd.to_datetime(df["first_seen"])
    df["last_seen"] = pd.to_datetime(df["last_seen"])
    df["source"] = df["source"].fillna("hellojob")
    df["url"] = df.apply(lambda r: f"https://boss.az/vacancies/{r['id'].removeprefix('boss-')}" if r["source"] == "boss"
                         else f"https://www.hellojob.az/vakansiya/{r['id']}", axis=1)
    for column in ["salary_from", "salary_to"]:
        df[column] = pd.to_numeric(df[column], errors="coerce") if column in df else float("nan")
    df["salary_mid"] = df[["salary_from", "salary_to"]].mean(axis=1)
    title_junior = df["title"].str.contains(JUNIOR_TITLE, flags=re.I, regex=True, na=False)
    low_exp = (df["min_experience_years"] <= 1) & ~df["seniority"].isin(["Senior", "Lead / Head"])
    df["experience"] = df["min_experience_years"].map(lambda y: "—" if pd.isna(y) else f"{y:.0f} il")
    df["junior"] = title_junior | (df["seniority"] == "Intern") | low_exp
    df["skills"] = df[SKILL_COLUMNS].apply(lambda r: ", ".join(c for c in SKILL_COLUMNS if r[c] and c not in LANGUAGES), axis=1)
    df["salary"] = df.apply(lambda r: "" if pd.isna(r["salary_mid"]) else
                            (f"{r['salary_from']:.0f}" + (f"–{r['salary_to']:.0f}" if r["salary_to"] != r["salary_from"] else "") + " ₼"),
                            axis=1)
    return df


def vacancy_table(data: pd.DataFrame, extra: dict | None = None) -> None:
    columns = {"title": "Vəzifə", "company": "Şirkət", "role_family": "Rol", "seniority": "Səviyyə",
               "experience": "Təcrübə",
               "salary": "Maaş", "skills": "Bacarıqlar",
               "first_seen": st.column_config.DateColumn("Tarix", format="DD.MM.YYYY"),
               "source": "Mənbə", "url": LINK}
    columns.update(extra or {})
    st.dataframe(data[list(columns)], column_config=columns, hide_index=True, width="stretch")


def bar(series: pd.Series, title: str, suffix: str = "") -> None:
    data = series.sort_values().reset_index()
    data.columns = ["label", "value"]
    fig = px.bar(data, x="value", y="label", orientation="h", text="value", title=title)
    fig.update_traces(marker_color=BLUE, texttemplate="%{text}" + suffix, textposition="outside", cliponaxis=False)
    fig.update_layout(xaxis_title=None, yaxis_title=None, height=90 + 32 * len(data),
                      margin=dict(l=0, r=40, t=50, b=0), xaxis=dict(showticklabels=False, showgrid=False))
    st.plotly_chart(fig, width="stretch")


df = load(HISTORY_PATH.stat().st_mtime)
latest = df["last_seen"].max()

st.title("Azərbaycanda IT vakansiyaları nə tələb edir?")
st.caption(f"Mənbələr: hellojob.az, boss.az · son yenilənmə: {latest:%d.%m.%Y} · hər gün avtomatik yenilənir")

with st.sidebar:
    st.header("Filtrlər")
    only_active = st.toggle("Yalnız aktiv vakansiyalar", value=True)
    sources = st.multiselect("Mənbə", sorted(df["source"].unique()), placeholder="Hamısı")
    families = st.multiselect("Rol", sorted(df["role_family"].dropna().unique()), placeholder="Hamısı")
    levels = st.multiselect("Səviyyə", [s for s in SENIORITY_ORDER if s in set(df["seniority"])], placeholder="Hamısı")

latest_by_source = df.groupby("source")["last_seen"].transform("max")
view = df[df["last_seen"] == latest_by_source] if only_active else df
if sources:
    view = view[view["source"].isin(sources)]
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

tab_skills, tab_search, tab_junior, tab_learn, tab_salary, tab_market, tab_trend = st.tabs(
    ["Bacarıqlar", "Vakansiyalar", "Junior / təcrübəçi", "Nə öyrənməliyəm?", "Maaşlar", "Şirkətlər", "Trend"])

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

with tab_salary:
    paid = view.dropna(subset=["salary_mid"])
    st.caption(f"Maaş yalnız {len(paid)} vakansiyada göstərilib ({len(paid) / len(view) * 100:.0f}%). "
               "Nəticələr bu vakansiyalara əsaslanır və bütün bazarı təmsil etməyə bilər.")
    if len(paid) >= 3:
        s1, s2, s3 = st.columns(3)
        s1.metric("Median maaş", f"{paid['salary_mid'].median():,.0f} ₼")
        s2.metric("Minimum", f"{paid['salary_from'].min():,.0f} ₼")
        s3.metric("Maksimum", f"{paid['salary_to'].max():,.0f} ₼")
        by_role = paid.groupby("role_family")["salary_mid"].agg(["median", "count"])
        by_role = by_role[by_role["count"] >= 2]["median"].round(0)
        if not by_role.empty:
            bar(by_role, "Rol üzrə median maaş (₼, ən azı 2 vakansiya)")
        st.dataframe(
            paid.sort_values("salary_mid", ascending=False)[["title", "company", "salary_from", "salary_to", "source", "url"]],
            column_config={
                "title": "Vəzifə", "company": "Şirkət",
                "salary_from": st.column_config.NumberColumn("Min (₼)", format="%d"),
                "salary_to": st.column_config.NumberColumn("Max (₼)", format="%d"),
                "source": "Mənbə", "url": LINK,
            },
            hide_index=True, width="stretch",
        )

with tab_search:
    q1, q2, q3 = st.columns([2, 2, 1])
    query = q1.text_input("Axtar", placeholder="vəzifə, şirkət və ya bacarıq: Java, ABB, Power BI...")
    companies = q2.multiselect("Şirkət", sorted(view["company"].dropna().unique()), placeholder="Hamısı")
    recent = q3.toggle("Son 7 gün", value=False)
    found = view
    if query:
        haystack = found["title"] + " " + found["company"].fillna("") + " " + found["skills"] + " " + found["category"].fillna("")
        found = found[haystack.str.contains(re.escape(query), case=False, na=False)]
    if companies:
        found = found[found["company"].isin(companies)]
    if recent:
        found = found[found["first_seen"] >= found["first_seen"].max() - pd.Timedelta(days=7)]
    st.caption(f"{len(found)} vakansiya")
    vacancy_table(found.sort_values("first_seen", ascending=False))

with tab_junior:
    juniors = view[view["junior"]]
    st.caption("Başlığında junior, təcrübəçi, intern, kiçik mütəxəssis yazılan və ya ən çox 1 il təcrübə istəyən vakansiyalar.")
    j1, j2, j3 = st.columns(3)
    j1.metric("Junior vakansiya", len(juniors))
    j2.metric("Bütün vakansiyaların", f"{len(juniors) / len(view) * 100:.0f}%")
    j3.metric("Təcrübə proqramı", int(juniors["title"].str.contains("təcrübə proqram|intern|trainee", case=False).sum()))
    if not juniors.empty:
        left, right = st.columns([1, 2])
        with left:
            junior_share = (juniors[SKILL_COLUMNS].drop(columns=LANGUAGES).mean() * 100).round(0)
            bar(junior_share[junior_share > 0].sort_values(ascending=False).head(10), "Junior vakansiyalarda bacarıqlar", "%")
        with right:
            vacancy_table(juniors.sort_values("first_seen", ascending=False))

with tab_learn:
    l1, l2 = st.columns([1, 2])
    roles = view["role_family"].value_counts()
    target = l1.selectbox("Hədəf rol", ["Bütün rollar"] + roles.index.tolist(),
                          format_func=lambda r: r if r == "Bütün rollar" else f"{r} ({roles[r]})")
    mine = l2.multiselect("Bildiyin bacarıqlar", SKILL_COLUMNS, default=["SQL", "Python", "English"], placeholder="Bacarıq seç")
    pool = view if target == "Bütün rollar" else view[view["role_family"] == target]
    required = pool[SKILL_COLUMNS]
    needed = required.sum(axis=1)

    def ready_count(skills: list[str]) -> int:
        have = required[skills].sum(axis=1) if skills else 0
        return int(((needed > 0) & (have / needed.where(needed > 0) >= 0.5)).sum())

    missing = (required.drop(columns=mine).mean() * 100).round(0).sort_values(ascending=False)
    missing = missing[missing > 0]
    top3 = missing.head(3).index.tolist()
    now, later = ready_count(mine), ready_count(mine + top3)
    m1, m2 = st.columns(2)
    m1.metric("Tələblərinin yarısını qarşıladığın vakansiyalar", f"{now} / {len(pool)}")
    if top3:
        m2.metric(f"{', '.join(top3)} öyrənsən", f"{later} / {len(pool)}", delta=f"+{later - now}")
    left, right = st.columns([1, 2])
    with left:
        if not missing.empty:
            bar(missing.head(10), "Öyrənməli bacarıqlar (% vakansiya)", "%")
        else:
            st.success("Bu rol üzrə tələb olunan bütün bacarıqları seçmisən.")
    with right:
        have = required[mine].sum(axis=1) if mine else 0
        matches = pool.assign(
            uyğunluq=(have / needed.where(needed > 0)).mul(100).round(0),
            çatışmayan=required.apply(lambda row: ", ".join(s for s in SKILL_COLUMNS if row[s] and s not in mine), axis=1),
        ).sort_values(["uyğunluq", "min_experience_years"], ascending=[False, True])
        st.dataframe(
            matches[["title", "company", "uyğunluq", "çatışmayan", "url"]],
            column_config={"title": "Vəzifə", "company": "Şirkət",
                           "uyğunluq": st.column_config.ProgressColumn("Uyğunluq", format="%d%%", min_value=0, max_value=100),
                           "çatışmayan": "Çatışmayan bacarıqlar", "url": LINK},
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
