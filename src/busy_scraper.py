import argparse
import json
import re
import time
from datetime import date

from scraper import RAW_DIR, clean, fetch, load_seen, make_session
from boss_scraper import HEADERS, html_text

BASE_URL = "https://busy.az"
SITEMAP = f"{BASE_URL}/sitemap/live-vacancies.xml"


def vacancy_id(url: str) -> str | None:
    match = re.search(r"/vacancy/(\d+)", url)
    return f"busy-{match.group(1)}" if match else None


def job_posting(html: str) -> dict | None:
    for block in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html, re.S):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        for item in data if isinstance(data, list) else [data]:
            if isinstance(item, dict) and item.get("@type") == "JobPosting":
                return item
    return None


def salary_range(posting: dict) -> tuple[float | None, float | None]:
    value = (posting.get("baseSalary") or {}).get("value") or {}
    if not isinstance(value, dict):
        return None, None
    low = value.get("minValue", value.get("value"))
    high = value.get("maxValue", value.get("value"))
    return low, high


def to_row(vid: str, posting: dict) -> dict:
    low, high = salary_range(posting)
    salary = "-".join(str(int(s)) for s in dict.fromkeys([low, high]) if s)
    address = ((posting.get("jobLocation") or {}).get("address") or {}) if isinstance(posting.get("jobLocation"), dict) else {}
    return {
        "id": vid,
        "slug": vid,
        "title": clean(posting.get("title", "")),
        "company": clean((posting.get("hiringOrganization") or {}).get("name", "")),
        "category": clean(posting.get("occupationalCategory") or ""),
        "date_posted": (posting.get("datePosted") or "")[:10],
        "valid_through": (posting.get("validThrough") or "")[:10],
        "employment_type": posting.get("employmentType") or "",
        "city": address.get("addressLocality", ""),
        "salary_raw": f"{salary} AZN" if salary else "",
        "salary_from": low,
        "salary_to": high,
        "description": html_text(posting.get("description")),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect active vacancies from busy.az")
    parser.add_argument("--delay", type=float, default=0.7)
    parser.add_argument("--full", action="store_true", help="re-download vacancies that were already seen")
    args = parser.parse_args()

    session = make_session()
    session.headers.update(HEADERS)
    xml = fetch(session, SITEMAP)
    urls = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml or "")
    ids = {vacancy_id(u): u for u in urls if vacancy_id(u)}
    if not ids:
        raise SystemExit("busy.az sitemap returned no vacancies; aborting without writing output")
    seen = set() if args.full else load_seen("busy")
    todo = {vid: url for vid, url in ids.items() if vid not in seen}
    print(f"Found {len(ids)} active vacancies, {len(todo)} new")

    rows = []
    for i, (vid, url) in enumerate(todo.items(), 1):
        html = fetch(session, url)
        time.sleep(args.delay)
        posting = job_posting(html or "")
        if posting is None:
            print(f"  skip {url}: no JobPosting data")
            continue
        rows.append(to_row(vid, posting))
        print(f"[{i}/{len(todo)}] {rows[-1]['title'][:70]}")

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    (RAW_DIR / f"busy_vacancies_{today}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=0), encoding="utf-8")
    (RAW_DIR / f"busy_active_{today}.txt").write_text("\n".join(ids), encoding="utf-8")
    print(f"Saved {len(rows)} new vacancies and {len(ids)} active ids")


if __name__ == "__main__":
    main()
