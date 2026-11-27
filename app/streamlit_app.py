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
TECH_COLUMNS = [c for c in SKILL_COLUMNS if c not in LANGUAGES]
SENIORITY_ORDER = ["Intern", "Junior / Mid", "Senior", "Lead / Head"]
JUNIOR_TITLE = r"junior|trainee|intern|təcrübəçi|təcrübə proqram|kiçik (?:mütəxəssis|proqramçı|analitik|mühəndis|developer)"
TELEGRAM = "https://t.me/az_it_jobs"
GITHUB = "https://github.com/rustamliyusif/az-data-jobs-analysis"
MATCH_SHARE = 0.5

PALETTE = {
    "light": {"ink": "#14232B", "muted": "#5B6B72", "caspian": "#0E6E74", "nar": "#C2304A",
              "quiet": "#C3D0D3", "surface": "#E6EEEE", "scale": ["#E6EEEE", "#0E6E74"]},
    "dark": {"ink": "#E4ECEE", "muted": "#93A4AA", "caspian": "#36B3B8", "nar": "#E8607A",
             "quiet": "#3A4D54", "surface": "#18262C", "scale": ["#18262C", "#1F7F84"]},
}

st.set_page_config(page_title="AZ IT Jobs — Bakıda IT vakansiyaları", page_icon="📊", layout="wide",
                   initial_sidebar_state="collapsed")

theme_type = getattr(getattr(st.context, "theme", None), "type", None) or "light"
C = PALETTE["dark" if theme_type == "dark" else "light"]

st.html(f"""
<style>
  .block-container {{ padding-top: 4.5rem; max-width: 1180px; }}
  .hero h1 {{ font-family: 'Unbounded', sans-serif; font-weight: 600; font-size: clamp(1.9rem, 4.2vw, 3.4rem);
             line-height: 1.12; letter-spacing: -0.02em; margin: 0 0 .9rem 0; max-width: 17ch; color: {C['ink']}; }}
  .hero h1 .count {{ color: {C['caspian']}; }}
  .hero p {{ font-size: 1.05rem; color: {C['muted']}; margin: 0; max-width: 62ch; }}
  .verdict {{ font-size: 1.2rem; line-height: 1.5; color: {C['ink']}; max-width: 60ch; margin: .2rem 0 0 0; }}
  .verdict b {{ font-family: 'Unbounded', sans-serif; font-weight: 600; color: {C['caspian']}; }}
  .verdict .next {{ color: {C['nar']}; font-weight: 600; }}
  .facts {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1.4rem;
            margin: .4rem 0 .2rem 0; }}
  .facts div {{ border-left: 3px solid {C['caspian']}; padding: .1rem 0 .1rem .9rem; color: {C['muted']};
                font-size: .98rem; line-height: 1.45; }}
  .facts b {{ display: block; color: {C['ink']}; font-family: 'Unbounded', sans-serif; font-weight: 500;
              font-size: 1.35rem; margin-bottom: .15rem; }}
  .ask {{ font-family: 'Unbounded', sans-serif; font-weight: 500; font-size: 1.25rem; margin: 1.6rem 0 .1rem 0;
          color: {C['ink']}; }}
  .foot {{ color: {C['muted']}; font-size: .9rem; }}
  .foot a {{ color: {C['caspian']}; }}
  @media (max-width: 640px) {{ .verdict {{ font-size: 1.05rem; }} }}
</style>
""")


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
    df["posted"] = pd.to_datetime(df["date_posted"], errors="coerce").fillna(df["first_seen"])
    newest = df["last_seen"].max()
    df["is_new"] = df["posted"] >= newest - pd.Timedelta(days=2)
    df["title_display"] = df["title"].where(~df["is_new"], "🆕 " + df["title"])
    title_junior = df["title"].str.contains(JUNIOR_TITLE, flags=re.I, regex=True, na=False)
    low_exp = (df["min_experience_years"] <= 1) & ~df["seniority"].isin(["Senior", "Lead / Head"])
    df["junior"] = title_junior | (df["seniority"] == "Intern") | low_exp
    df["experience"] = df["min_experience_years"].map(lambda y: "—" if pd.isna(y) else f"{y:.0f} il")
    df["skills"] = df[TECH_COLUMNS].apply(lambda r: ", ".join(c for c in TECH_COLUMNS if r[c]), axis=1)
    df["salary"] = df.apply(lambda r: "" if pd.isna(r["salary_mid"]) else
                            f"{r['salary_from']:.0f}" + ("" if r["salary_to"] == r["salary_from"] else f"–{r['salary_to']:.0f}") + " ₼",
                            axis=1)
    return df


def style(fig, height: int) -> None:
    fig.update_layout(height=height, margin=dict(l=0, r=48, t=8, b=0), showlegend=False,
                      font=dict(family="Onest, sans-serif", color=C["ink"], size=13),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      xaxis=dict(visible=False),
                      yaxis=dict(title=None, tickfont=dict(size=13), automargin=True, showticklabels=True, ticksuffix="  "))
    st.plotly_chart(fig, width="stretch", theme=None, config={"displayModeBar": False})


def skill_bars(share: pd.Series, mine: list[str], suffix: str = "%") -> None:
    data = share.sort_values().reset_index()
    data.columns = ["skill", "value"]
    data["color"] = data["skill"].map(lambda s: C["caspian"] if s in mine else C["quiet"])
    fig = px.bar(data, x="value", y="skill", orientation="h", text="value")
    fig.update_traces(marker_color=data["color"], texttemplate="%{text:.0f}" + suffix, textposition="outside",
                      cliponaxis=False, hovertemplate="%{y}: %{x:.0f}" + suffix + "<extra></extra>")
    style(fig, 40 + 30 * len(data))


def plain_bars(series: pd.Series, suffix: str = "") -> None:
    data = series.sort_values().reset_index()
    data.columns = ["label", "value"]
    fig = px.bar(data, x="value", y="label", orientation="h", text="value")
    fig.update_traces(marker_color=C["caspian"], texttemplate="%{text:,.0f}" + suffix, textposition="outside",
                      cliponaxis=False, hovertemplate="%{y}: %{x:,.0f}" + suffix + "<extra></extra>")
    style(fig, 40 + 30 * len(data))


def vacancy_table(data: pd.DataFrame) -> None:
    columns = {"title_display": "Vəzifə", "company": "Şirkət", "role_family": "Rol", "experience": "Təcrübə",
               "salary": "Maaş", "skills": "Bacarıqlar",
               "posted": st.column_config.DateColumn("Tarix", format="DD.MM.YYYY"),
               "url": st.column_config.LinkColumn("Elan", display_text="Aç")}
    st.dataframe(data[list(columns)], column_config=columns, hide_index=True, width="stretch")


def coverage(pool: pd.DataFrame, skills: list[str]) -> pd.Series:
    required = pool[SKILL_COLUMNS]
    needed = required.sum(axis=1)
    have = required[skills].sum(axis=1) if skills else 0
    return (have / needed.where(needed > 0)).fillna(0)


def best_next(pool: pd.DataFrame, skills: list[str]) -> tuple[str | None, int]:
    base = int((coverage(pool, skills) >= MATCH_SHARE).sum())
    gains = {s: int((coverage(pool, skills + [s]) >= MATCH_SHARE).sum()) - base
             for s in SKILL_COLUMNS if s not in skills and pool[s].any()}
    if not gains:
        return None, 0
    skill = max(gains, key=gains.get)
    return skill, gains[skill]


df = load(HISTORY_PATH.stat().st_mtime)
latest = df["last_seen"].max()
active = df[df["last_seen"] == df.groupby("source")["last_seen"].transform("max")]

with st.sidebar:
    st.subheader("Filtrlər")
    only_active = st.toggle("Yalnız aktiv vakansiyalar", value=True)
    sources = st.multiselect("Mənbə", sorted(df["source"].unique()), placeholder="Hamısı",
                             format_func=lambda s: {"hellojob": "hellojob.az", "boss": "boss.az"}.get(s, s))
    families = st.multiselect("Rol", sorted(df["role_family"].dropna().unique()), placeholder="Hamısı")
    levels = st.multiselect("Səviyyə", [s for s in SENIORITY_ORDER if s in set(df["seniority"])], placeholder="Hamısı")

view = active if only_active else df
if sources:
    view = view[view["source"].isin(sources)]
if families:
    view = view[view["role_family"].isin(families)]
if levels:
    view = view[view["seniority"].isin(levels)]

st.html(f"""
<div class="hero">
  <h1>Bakıda bu gün <span class="count">{len(active)}</span> IT vakansiyası açıqdır.</h1>
  <p>{active['company'].nunique()} şirkətin elanlarını hellojob.az və boss.az-dan hər səhər yığırıq və
     hər elandan bacarıqları çıxarırıq. Bildiyin bacarıqları seç, bazarın sənə nə dediyinə bax.</p>
</div>
""")

if view.empty:
    st.warning("Seçdiyin filtrlərə uyğun vakansiya yoxdur. Sol paneldə filtrləri dəyiş.")
    st.stop()

demand = (view[TECH_COLUMNS].mean() * 100).sort_values(ascending=False)
pickable = demand[demand > 0].head(24).index.tolist() + LANGUAGES
st.html('<h3 class="ask">Nə bilirsən?</h3>')
mine = st.pills("Nə bilirsən?", pickable, label_visibility="collapsed", selection_mode="multi", default=["SQL", "Python", "English"], key="mine")
mine = list(mine or [])

ready = int((coverage(view, mine) >= MATCH_SHARE).sum())
skill, gain = best_next(view, mine)
next_line = (f' Növbəti addım: <span class="next">{skill}</span> öyrənsən, bu say <b>{ready + gain}</b> olur.'
             if skill and gain > 0 else "")
if mine:
    st.html(f'<p class="verdict">Bu bacarıqlarla <b>{ready}</b> vakansiyanın tələblərinin ən azı yarısını qarşılayırsan.{next_line}</p>')
else:
    st.html('<p class="verdict">Yuxarıdan ən azı bir bacarıq seç.</p>')

top_skill = demand.index[0]
recent = int((view["posted"] >= latest - pd.Timedelta(days=7)).sum())
juniors = view[view["junior"]]
internships = int(juniors["title"].str.contains("təcrübə proqram|intern|trainee", case=False).sum())
st.html(f"""
<div class="facts">
  <div><b>{top_skill}</b>ən çox istənən bacarıqdır: hər 100 vakansiyadan {demand.iloc[0]:.0f}-ində yazılıb.</div>
  <div><b>{recent} yeni elan</b>son 7 gündə dərc olunub.</div>
  <div><b>{len(juniors)} junior vakansiya</b>təcrübəsi az olanlar üçündür, {internships}-i təcrübə proqramıdır.</div>
</div>
""")

st.write("")
tab_skills, tab_search, tab_junior, tab_learn, tab_salary, tab_market, tab_trend = st.tabs(
    ["Bacarıqlar", "Vakansiyalar", "Junior", "Nə öyrənməli?", "Maaşlar", "Şirkətlər", "Trend"])

with tab_skills:
    st.caption("Rəngli zolaqlar sənin seçdiyin bacarıqlardır.")
    left, right = st.columns([3, 2], gap="large")
    with left:
        st.markdown("**Ən çox tələb olunan 20 bacarıq**, vakansiyaların faizi ilə")
        skill_bars(demand[demand > 0].head(20), mine)
    with right:
        st.markdown("**Dil tələbləri**")
        skill_bars((view[LANGUAGES].mean() * 100), mine)
    top_roles = view["role_family"].value_counts().head(10).index
    top_skills = demand.head(12).index.tolist()
    by_role = view[view["role_family"].isin(top_roles)].groupby("role_family")[top_skills].mean().mul(100).round(0)
    by_role = by_role[by_role.sum(axis=1) > 0]
    if len(by_role) > 1:
        st.markdown("**Hər rol nə istəyir?** Xanadakı rəqəm həmin rolun elanlarının neçə faizində bacarığın yazıldığını göstərir.")
        fig = px.imshow(by_role, text_auto=True, aspect="auto", color_continuous_scale=C["scale"])
        fig.update_traces(hovertemplate="%{y} · %{x}: %{z:.0f}%<extra></extra>")
        fig.update_layout(coloraxis_showscale=False, height=80 + 42 * len(by_role), margin=dict(l=0, r=0, t=0, b=0),
                          font=dict(family="Onest, sans-serif", color=C["ink"], size=13),
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          xaxis=dict(title=None, side="top", automargin=True),
                          yaxis=dict(title=None, automargin=True, ticksuffix="  "))
        st.plotly_chart(fig, width="stretch", theme=None, config={"displayModeBar": False})

with tab_search:
    q1, q2, q3 = st.columns([3, 2, 1], vertical_alignment="bottom")
    query = q1.text_input("Axtar", placeholder="Vəzifə, şirkət və ya bacarıq: Java, ABB, Power BI")
    companies = q2.multiselect("Şirkət", sorted(view["company"].dropna().unique()), placeholder="Hamısı")
    last_week = q3.toggle("Son 7 gün")
    found = view
    if query:
        haystack = found["title"] + " " + found["company"].fillna("") + " " + found["skills"] + " " + found["category"].fillna("")
        found = found[haystack.str.contains(re.escape(query), case=False, na=False)]
    if companies:
        found = found[found["company"].isin(companies)]
    if last_week:
        found = found[found["posted"] >= latest - pd.Timedelta(days=7)]
    c1, c2 = st.columns([4, 1], vertical_alignment="center")
    c1.caption(f"{len(found)} vakansiya. 🆕 son 2 gündə dərc olunub.")
    export = found[["title", "company", "role_family", "seniority", "experience", "salary", "skills", "posted", "source", "url"]]
    c2.download_button("CSV yüklə", export.to_csv(index=False).encode("utf-8-sig"),
                       file_name="az_it_vakansiyalar.csv", mime="text/csv", width="stretch")
    if found.empty:
        st.info("Bu axtarışa uyğun vakansiya tapılmadı. Başqa söz yoxla və ya filtrləri təmizlə.")
    else:
        vacancy_table(found.sort_values("posted", ascending=False))

with tab_junior:
    st.caption("Başlığında junior, təcrübəçi, intern, kiçik mütəxəssis yazılan və ya ən çox 1 il təcrübə istəyən vakansiyalar.")
    if juniors.empty:
        st.info("Seçdiyin filtrlərdə junior vakansiya yoxdur.")
    else:
        left, right = st.columns([1, 2], gap="large")
        with left:
            st.markdown("**Junior elanlarda bacarıqlar**")
            share = juniors[TECH_COLUMNS].mean() * 100
            skill_bars(share[share > 0].sort_values(ascending=False).head(10), mine)
        with right:
            vacancy_table(juniors.sort_values("posted", ascending=False))

with tab_learn:
    roles = view["role_family"].value_counts()
    target = st.selectbox("Hansı rolda işləmək istəyirsən?", ["Bütün rollar"] + roles.index.tolist(),
                          format_func=lambda r: r if r == "Bütün rollar" else f"{r} ({roles[r]} vakansiya)")
    pool = view if target == "Bütün rollar" else view[view["role_family"] == target]
    missing = (pool[SKILL_COLUMNS].drop(columns=mine).mean() * 100).sort_values(ascending=False)
    missing = missing[missing > 0]
    pool_ready = int((coverage(pool, mine) >= MATCH_SHARE).sum())
    st.caption(f"Seçdiyin bacarıqlarla bu roldakı {len(pool)} vakansiyadan {pool_ready}-nə uyğunsan. "
               "Bacarıqları yuxarıdakı \"Nə bilirsən?\" hissəsindən dəyiş.")
    left, right = st.columns([1, 2], gap="large")
    with left:
        st.markdown("**Sənə çatışmayan bacarıqlar**")
        if missing.empty:
            st.success("Bu rol üçün tələb olunan bütün bacarıqları seçmisən.")
        else:
            skill_bars(missing.head(10), [])
    with right:
        matches = pool.assign(
            uyğunluq=coverage(pool, mine).mul(100).round(0),
            çatışmayan=pool[SKILL_COLUMNS].apply(lambda r: ", ".join(s for s in SKILL_COLUMNS if r[s] and s not in mine), axis=1),
        ).sort_values(["uyğunluq", "min_experience_years"], ascending=[False, True])
        st.dataframe(
            matches[["title_display", "company", "uyğunluq", "çatışmayan", "url"]],
            column_config={"title_display": "Vəzifə", "company": "Şirkət",
                           "uyğunluq": st.column_config.ProgressColumn("Uyğunluq", format="%d%%", min_value=0, max_value=100),
                           "çatışmayan": "Çatışmayan", "url": st.column_config.LinkColumn("Elan", display_text="Aç")},
            hide_index=True, width="stretch",
        )

with tab_salary:
    paid = view.dropna(subset=["salary_mid"])
    st.caption(f"Maaş yalnız {len(paid)} vakansiyada göstərilib ({len(paid) / len(view) * 100:.0f}%). "
               "Rəqəmlər bu elanlara əsaslanır və bütün bazarı təmsil etməyə bilər.")
    if len(paid) < 3:
        st.info("Bu filtrlərdə maaş göstərilən elan azdır. Filtrləri genişləndir.")
    else:
        s1, s2, s3 = st.columns(3)
        s1.metric("Median maaş", f"{paid['salary_mid'].median():,.0f} ₼")
        s2.metric("Ən aşağı", f"{paid['salary_from'].min():,.0f} ₼")
        s3.metric("Ən yuxarı", f"{paid['salary_to'].max():,.0f} ₼")
        by_role = paid.groupby("role_family")["salary_mid"].agg(["median", "count"])
        by_role = by_role[by_role["count"] >= 2]["median"].round(0)
        left, right = st.columns([1, 2], gap="large")
        with left:
            if not by_role.empty:
                st.markdown("**Rol üzrə median maaş** (ən azı 2 elan)")
                plain_bars(by_role, " ₼")
        with right:
            vacancy_table(paid.sort_values("salary_mid", ascending=False))

with tab_market:
    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("**Ən çox işə götürən şirkətlər**")
        plain_bars(view["company"].value_counts().head(15))
    with right:
        st.markdown("**Rollar**")
        plain_bars(view["role_family"].value_counts())
        st.markdown("**Səviyyə**")
        plain_bars(view["seniority"].value_counts().reindex(SENIORITY_ORDER).dropna().astype(int))

with tab_trend:
    if df["last_seen"].nunique() < 7:
        st.info("Trendlər üçün data hər gün yığılır. Bir neçə həftədən sonra burada bacarıqların necə dəyişdiyini görəcəksən.")
    weekly = view[view["posted"] >= latest - pd.Timedelta(weeks=12)].set_index("posted").resample("W")["id"].count()
    if len(weekly) > 1:
        st.markdown("**Həftəlik dərc olunan vakansiyalar**")
        fig = px.bar(weekly.reset_index(), x="posted", y="id")
        fig.update_traces(marker_color=C["caspian"], hovertemplate="%{x|%d.%m}: %{y}<extra></extra>")
        fig.update_layout(height=320, margin=dict(l=0, r=0, t=8, b=0), font=dict(family="Onest, sans-serif", color=C["ink"]),
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          xaxis=dict(title=None, tickformat="%d.%m"), yaxis=dict(title=None, gridcolor=C["surface"]))
        st.plotly_chart(fig, width="stretch", theme=None, config={"displayModeBar": False})

st.divider()
st.html(f"""
<p class="foot">Son yenilənmə {latest:%d.%m.%Y}. Yeni vakansiyalar hər səhər
<a href="{TELEGRAM}" target="_blank">Telegram kanalında</a> paylaşılır. Kod <a href="{GITHUB}" target="_blank">GitHub-dadır</a>.
Hazırladı: Yusif Rustamli. Bacarıqlar elan mətnindən açar sözlərlə tapılır, nəticələr təxminidir.</p>
""")
