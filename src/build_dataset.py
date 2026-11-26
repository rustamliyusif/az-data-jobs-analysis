import json
import sys
from pathlib import Path

import pandas as pd

from features import build_features

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
SNAPSHOT_PATH = PROCESSED / "data_roles.csv"
HISTORY_PATH = PROCESSED / "vacancies_history.csv"


def update_history(snapshot: pd.DataFrame, date: str, source: str = "hellojob") -> pd.DataFrame:
    current = snapshot.drop(columns=["snapshot"]).assign(source=source, first_seen=date, last_seen=date)
    if not HISTORY_PATH.exists():
        return current
    history = pd.read_csv(HISTORY_PATH, dtype={"first_seen": str, "last_seen": str})
    previous = history[["id", "source", "first_seen"]]
    current = current.drop(columns=["first_seen"]).merge(previous, on=["id", "source"], how="left")
    current["first_seen"] = current["first_seen"].fillna(date)
    gone = history[~history.set_index(["id", "source"]).index.isin(current.set_index(["id", "source"]).index)]
    return pd.concat([gone, current], ignore_index=True).sort_values(["first_seen", "id"])


def main() -> None:
    raw_file = Path(sys.argv[1]) if len(sys.argv) > 1 else sorted(RAW_DIR.glob("hellojob_vacancies_*.json"))[-1]
    raw = pd.DataFrame(json.loads(raw_file.read_text(encoding="utf-8")))
    date = raw_file.stem.rsplit("_", 1)[-1]
    features = build_features(raw)
    features["snapshot"] = date
    PROCESSED.mkdir(parents=True, exist_ok=True)
    features.to_csv(SNAPSHOT_PATH, index=False)
    history = update_history(features, date)
    history.to_csv(HISTORY_PATH, index=False)
    summary = {
        "snapshot": date,
        "vacancies_scraped": len(raw),
        "it_roles": len(features),
        "salary_disclosed_all": int(raw["salary_raw"].str.contains(r"\d").sum()),
        "history_total": len(history),
    }
    (PROCESSED / "summary.json").write_text(json.dumps(summary, indent=2))
    print(summary)


if __name__ == "__main__":
    main()
