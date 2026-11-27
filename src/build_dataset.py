import json
import sys
from pathlib import Path

import pandas as pd

from features import ROLE_FAMILIES, SENIORITY, build_features, duplicate_key, first_match, is_it_role

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
HISTORY_PATH = PROCESSED / "vacancies_history.csv"
SEEN_PATH = PROCESSED / "seen_ids.csv"
SOURCES = ["hellojob", "boss", "busy"]


def latest_date(source: str) -> str | None:
    files = sorted(RAW_DIR.glob(f"{source}_active_*.txt"))
    return files[-1].stem.rsplit("_", 1)[-1] if files else None


def load_raw(source: str, date: str) -> tuple[pd.DataFrame, set[str]]:
    raw_file = RAW_DIR / f"{source}_vacancies_{date}.json"
    raw = pd.DataFrame(json.loads(raw_file.read_text(encoding="utf-8"))) if raw_file.exists() else pd.DataFrame()
    active = set((RAW_DIR / f"{source}_active_{date}.txt").read_text(encoding="utf-8").split())
    return raw, active


def relabel(history: pd.DataFrame) -> pd.DataFrame:
    categories = history["category"].fillna("") if "category" in history else pd.Series("", index=history.index)
    history = history[[is_it_role(t, c) for t, c in zip(history["title"], categories)]].copy()
    history["role_family"] = history["title"].apply(lambda t: first_match(t, ROLE_FAMILIES))
    history["seniority"] = history["title"].apply(lambda t: first_match(t, SENIORITY))
    history["dup_key"] = [duplicate_key(t, c) for t, c in zip(history["title"], history["company"].fillna(""))]
    return history


def main() -> None:
    history = pd.read_csv(HISTORY_PATH, dtype={"first_seen": str, "last_seen": str}) if HISTORY_PATH.exists() else pd.DataFrame()
    seen = pd.read_csv(SEEN_PATH, dtype=str) if SEEN_PATH.exists() else pd.DataFrame(columns=["source", "id", "first_seen"])
    summary = {}

    for source in SOURCES:
        date = sys.argv[1] if len(sys.argv) > 1 else latest_date(source)
        if date is None or not (RAW_DIR / f"{source}_active_{date}.txt").exists():
            print(f"{source}: no data for {date}, skipped")
            continue
        raw, active = load_raw(source, date)
        if not history.empty:
            mask = (history["source"] == source) & history["id"].isin(active)
            history.loc[mask, "last_seen"] = date
        new_ids = set(raw["id"]) if not raw.empty else set()
        if not raw.empty:
            features = build_features(raw).assign(source=source, last_seen=date)
            if history.empty:
                features["first_seen"] = date
            else:
                first_seen = history.set_index("id")["first_seen"]
                features["first_seen"] = features["id"].map(first_seen).fillna(date)
                history = history[~history["id"].isin(features["id"])]
            history = pd.concat([history, features], ignore_index=True)
        fresh = new_ids - set(seen.loc[seen["source"] == source, "id"])
        seen = pd.concat([seen, pd.DataFrame({"source": source, "id": sorted(fresh), "first_seen": date})],
                         ignore_index=True)
        summary[source] = {"date": date, "active_listings": len(active), "downloaded": len(raw)}

    history = relabel(history).sort_values(["first_seen", "source", "id"])
    PROCESSED.mkdir(parents=True, exist_ok=True)
    history.to_csv(HISTORY_PATH, index=False)
    seen.sort_values(["source", "id"]).to_csv(SEEN_PATH, index=False)
    for source, stats in summary.items():
        stats["it_active"] = int(((history["source"] == source) & (history["last_seen"] == stats["date"])).sum())
    summary["history_total"] = len(history)
    (PROCESSED / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(summary)


if __name__ == "__main__":
    main()
