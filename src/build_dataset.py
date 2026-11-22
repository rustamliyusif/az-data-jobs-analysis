import json
import sys
from pathlib import Path

import pandas as pd

from features import build_features

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
OUT_PATH = ROOT / "data" / "processed" / "data_roles.csv"


def main() -> None:
    raw_file = Path(sys.argv[1]) if len(sys.argv) > 1 else sorted(RAW_DIR.glob("hellojob_vacancies_*.json"))[-1]
    raw = pd.DataFrame(json.loads(raw_file.read_text(encoding="utf-8")))
    features = build_features(raw)
    features["snapshot"] = raw_file.stem.rsplit("_", 1)[-1]
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(OUT_PATH, index=False)
    summary = {
        "snapshot": features["snapshot"].iloc[0],
        "vacancies_scraped": len(raw),
        "data_roles": len(features),
        "salary_disclosed_all": int(raw["salary_raw"].str.contains(r"\d").sum()),
    }
    (OUT_PATH.parent / "summary.json").write_text(json.dumps(summary, indent=2))
    print(summary)


if __name__ == "__main__":
    main()
