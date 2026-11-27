import argparse
import json
import os
from html import escape
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
HISTORY_PATH = ROOT / "data" / "processed" / "vacancies_history.csv"
SUMMARY_PATH = ROOT / "data" / "processed" / "summary.json"
DASHBOARD = "https://az-data-jobs.streamlit.app"
MAX_ITEMS = 40
CHUNK = 3800


def vacancy_url(row: pd.Series) -> str:
    if row["source"] == "boss":
        return f"https://boss.az/vacancies/{row['id'].removeprefix('boss-')}"
    return f"https://www.hellojob.az/vakansiya/{row['id']}"


def salary_text(row: pd.Series) -> str:
    low, high = row.get("salary_from"), row.get("salary_to")
    if pd.isna(low):
        return ""
    return f" · {low:.0f}{'' if pd.isna(high) or high == low else f'–{high:.0f}'} ₼"


def new_vacancies() -> tuple[str, pd.DataFrame]:
    summary = json.loads(SUMMARY_PATH.read_text())
    dates = {source: stats["date"] for source, stats in summary.items() if isinstance(stats, dict)}
    history = pd.read_csv(HISTORY_PATH, dtype={"first_seen": str, "last_seen": str})
    is_new = history.apply(lambda r: dates.get(r["source"]) == r["first_seen"], axis=1)
    return max(dates.values()), history[is_new].sort_values(["role_family", "title"])


def build_messages(date: str, rows: pd.DataFrame) -> list[str]:
    day = pd.Timestamp(date).strftime("%d.%m.%Y")
    header = f"🆕 <b>Yeni IT vakansiyaları — {day}</b> ({len(rows)})\n"
    lines = [
        f"• <a href=\"{vacancy_url(r)}\">{escape(r['title'])}</a> — {escape(str(r['company']))}{salary_text(r)}"
        for _, r in rows.head(MAX_ITEMS).iterrows()
    ]
    footer = f"\n📊 Bütün vakansiyalar və analiz: {DASHBOARD}"
    if len(rows) > MAX_ITEMS:
        footer = f"\n…və daha {len(rows) - MAX_ITEMS} vakansiya." + footer
    messages, current = [], header
    for line in lines:
        if len(current) + len(line) + 1 > CHUNK:
            messages.append(current)
            current = ""
        current += "\n" + line
    messages.append(current + "\n" + footer)
    return messages


WELCOME = (
    "👋 <b>AZ IT Vakansiyaları</b>\n\n"
    "Hər gün səhər saat 08:00 radələrində hellojob.az və boss.az-da yeni çıxan IT vakansiyaları burada paylaşılır.\n\n"
    f"📊 Bacarıqlar, maaşlar və bütün vakansiyalar: {DASHBOARD}"
)


def send(token: str, chat_id: str, text: str) -> None:
    response = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", timeout=20,
                             data={"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                                   "disable_web_page_preview": "true"})
    if not response.ok:
        raise SystemExit(f"Telegram error {response.status_code}: {response.text}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Send today's new IT vacancies to a Telegram channel")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--welcome", action="store_true", help="send the channel introduction message")
    args = parser.parse_args()
    token, chat_id = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")

    if args.welcome:
        if not token or not chat_id:
            raise SystemExit("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set")
        send(token, chat_id, WELCOME)
        print("Welcome message sent")
        return

    date, rows = new_vacancies()
    if rows.empty:
        print("No new vacancies today")
        return
    messages = build_messages(date, rows)
    if args.dry_run:
        print("\n\n=====\n\n".join(messages))
        return
    if not token or not chat_id:
        print("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set, skipping")
        return
    for text in messages:
        send(token, chat_id, text)
    print(f"Sent {len(rows)} vacancies in {len(messages)} message(s)")


if __name__ == "__main__":
    main()
