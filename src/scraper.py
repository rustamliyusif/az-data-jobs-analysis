import argparse
import json
import re
import time
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://www.hellojob.az"
QUERIES = ["data", "analitik", "analyst", "power bi", "sql", "python", "developer", "proqramçı",
           "backend", "frontend", "full stack", "java", ".net", "php", "javascript", "react", "android",
           "ios", "flutter", "mobil", "devops", "cloud", "sistem administratoru", "şəbəkə", "network",
           "kibertəhlükəsizlik", "security", "qa", "tester", "ui/ux", "product owner", "1c", "sap",
           "texniki dəstək", "IT", "süni intellekt", "machine learning", "software"]
HEADERS = {"User-Agent": "Mozilla/5.0 (portfolio research project; contact via GitHub)"}
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    retry = Retry(total=4, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504],
                  allowed_methods=["GET"], respect_retry_after_header=True)
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def fetch(session: requests.Session, url: str, **kwargs) -> str | None:
    try:
        response = session.get(url, timeout=20, **kwargs)
        response.raise_for_status()
        return response.text
    except requests.RequestException as error:
        print(f"  skip {url}: {error}")
        return None


def clean(text: str) -> str:
    text = re.sub(r"https?://\S+", "", text or "")
    return re.sub(r"\s+", " ", text).strip()


def collect_vacancy_paths(session: requests.Session, max_pages: int = 6, delay: float = 0.5) -> list[str]:
    paths: set[str] = set()
    for query in QUERIES:
        for page in range(1, max_pages + 1):
            html = fetch(session, f"{BASE_URL}/vakansiyalar", params={"q": query, "page": page})
            if html is None:
                break
            soup = BeautifulSoup(html, "html.parser")
            found = {a["href"].split("?")[0].replace(BASE_URL, "")
                     for a in soup.select("a[href*='/vakansiya/']")}
            before = len(paths)
            paths |= found
            if len(paths) == before:
                break
            time.sleep(delay)
    return sorted(paths)


def parse_job_posting(soup: BeautifulSoup) -> dict:
    for script in soup.select("script[type='application/ld+json']"):
        try:
            data = json.loads(script.string or "")
        except json.JSONDecodeError:
            continue
        items = data if isinstance(data, list) else data.get("@graph", [data])
        for item in items:
            if item.get("@type") == "JobPosting":
                return item
    return {}


def parse_vacancy(html: str, path: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    job = parse_job_posting(soup)
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    page_text = clean(soup.get_text(" "))
    salary = re.search(r"Maaş\s*(.{1,60}?)\s*Bitmə tarixi", page_text)
    home_link = soup.find("a", string=re.compile(r"^\s*Ana səhifə\s*$"))
    crumbs = []
    if home_link:
        container = home_link.find_parent(["nav", "ol", "ul", "div"])
        crumbs = list(dict.fromkeys(el.get_text(strip=True) for el in container.find_all(["a", "span"])
                                    if el.get_text(strip=True)))
    location = (job.get("jobLocation") or {}).get("address", {})
    description = BeautifulSoup(job.get("description", ""), "html.parser").get_text(" ")
    return {
        "id": path.replace("/vakansiya/", ""),
        "slug": path.replace("/vakansiya/", ""),
        "title": clean(job.get("title", "")),
        "company": clean((job.get("hiringOrganization") or {}).get("name", "")),
        "category": " > ".join(crumbs),
        "date_posted": job.get("datePosted", ""),
        "valid_through": (job.get("validThrough") or "")[:10],
        "employment_type": job.get("employmentType", ""),
        "city": location.get("addressLocality", ""),
        "salary_raw": salary.group(1).strip() if salary else "",
        "description": clean(description),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect IT vacancies from hellojob.az")
    parser.add_argument("--delay", type=float, default=0.5, help="seconds between requests")
    args = parser.parse_args()

    session = make_session()
    paths = collect_vacancy_paths(session, delay=args.delay)
    print(f"Found {len(paths)} vacancy pages")

    rows = []
    for i, path in enumerate(paths, 1):
        html = fetch(session, BASE_URL + path)
        time.sleep(args.delay)
        if html is None:
            continue
        row = parse_vacancy(html, path)
        if not row["title"]:
            print(f"  skip {path}: no JobPosting data")
            continue
        rows.append(row)
        print(f"[{i}/{len(paths)}] {row['title'][:70]}")

    if not rows:
        raise SystemExit("No vacancies collected; aborting without writing output")

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out = RAW_DIR / f"hellojob_vacancies_{date.today().isoformat()}.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"Saved {len(rows)} vacancies to {out}")


if __name__ == "__main__":
    main()
