import json
import re
import time
from datetime import date
from html import unescape

from bs4 import BeautifulSoup

from scraper import RAW_DIR, clean, fetch, make_session

BASE_URL = "https://boss.az"
IT_CATEGORIES = {
    "38": "İnformasiya texnologiyaları",
    "66": "Sistem idarəetməsi",
    "67": "Məlumat bazasının idarə edilməsi və inkişafı",
    "68": "İT mütəxəssisi / məsləhətçi",
    "69": "Proqramlaşdırma",
    "70": "İT layihələrin idarə edilməsi",
    "71": "Texniki avadanlıq mütəxəssisi",
    "72": "Proqram təminatı mühəndisi",
    "159": "Veb-dizayn",
    "277": "UI/UX dizayner",
}
SEARCH_CATEGORIES = ["38", "159", "277"]
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"}


def html_text(value: str | None) -> str:
    return clean(BeautifulSoup(unescape(value or ""), "html.parser").get_text(" "))


def extract_vacancies(html: str) -> dict[str, dict]:
    decoder = json.JSONDecoder()
    found = {}
    for match in re.finditer(r'\{"__typename":"Vacancy"', html):
        try:
            obj, _ = decoder.raw_decode(html, match.start())
        except json.JSONDecodeError:
            continue
        if obj.get("id") and obj.get("positionName"):
            found[obj["id"]] = obj
    return found


def has_next_page(html: str) -> bool:
    match = re.search(r'"pageInfo":\{"__typename":"PageInfo","endCursor":"[^"]*","hasNextPage":(true|false)', html)
    return bool(match and match.group(1) == "true")


def to_row(v: dict) -> dict:
    salary_from, salary_to = v.get("salaryFrom"), v.get("salaryTo")
    salary = "-".join(str(s) for s in dict.fromkeys([salary_from, salary_to]) if s)
    text = " ".join(html_text(v.get(k)) for k in ["description", "requirements", "responsibilities", "jobDescription"])
    return {
        "id": f"boss-{v['id']}",
        "slug": f"boss-{v['id']}",
        "title": clean(v.get("positionName", "")),
        "company": clean(v.get("name", "")),
        "category": IT_CATEGORIES.get(str(v.get("categoryId")), ""),
        "date_posted": (v.get("bumpedAt") or v.get("createdAt") or "")[:10],
        "valid_through": "",
        "employment_type": "",
        "city": v.get("location") or "",
        "salary_raw": f"{salary} AZN" if salary else "",
        "salary_from": salary_from,
        "salary_to": salary_to,
        "description": clean(text),
    }


def main() -> None:
    session = make_session()
    session.headers.update(HEADERS)
    vacancies: dict[str, dict] = {}
    for category in SEARCH_CATEGORIES:
        for page in range(1, 21):
            html = fetch(session, f"{BASE_URL}/search/vacancies", params={"categoryIds": category, "page": page})
            if html is None:
                break
            batch = extract_vacancies(html)
            new = {k: v for k, v in batch.items() if k not in vacancies}
            vacancies.update(batch)
            print(f"category {category} page {page}: {len(batch)} vacancies")
            time.sleep(1.0)
            if not new or not has_next_page(html):
                break

    rows = [to_row(v) for v in vacancies.values() if str(v.get("categoryId")) in IT_CATEGORIES]
    if not rows:
        raise SystemExit("No boss.az vacancies collected; aborting without writing output")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    (RAW_DIR / f"boss_vacancies_{today}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=0), encoding="utf-8")
    (RAW_DIR / f"boss_active_{today}.txt").write_text("\n".join(r["id"] for r in rows), encoding="utf-8")
    print(f"Saved {len(rows)} boss.az vacancies")


if __name__ == "__main__":
    main()
