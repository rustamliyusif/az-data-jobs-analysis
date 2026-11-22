import re

import pandas as pd

DATA_ROLE_PATTERN = r"data|analitik|analyst|analitika|məlumat bazası|reporting|hesabatlı|scientist|model"
EXCLUDE_PATTERN = r"^satış|kredit|lombard|\bSOC\b"

SKILLS = {
    "SQL": r"\bsql\b|t-sql|pl/sql",
    "Excel": r"\bexcel\b",
    "Power BI": r"power\s?bi",
    "Tableau": r"\btableau\b",
    "Qlik": r"\bqlik",
    "Python": r"\bpython\b",
    "R": r"\bR\b(?=[\s,/)])",
    "SAS": r"\bSAS\b",
    "DAX": r"\bDAX\b",
    "ETL": r"\betl\b|\bssis\b",
    "Data warehouse": r"\bdwh\b|data warehouse|anbar",
    "Statistics": r"statisti",
    "Machine learning": r"machine learning|maşın öyrənmə|\bML\b",
    "LLM / GenAI": r"\bllm|genai|generativ",
    "BPMN / UML": r"\bbpmn\b|\buml\b",
    "Jira / Confluence": r"\bjira\b|confluence",
    "Agile / Scrum": r"\bagile\b|\bscrum\b",
    "API": r"\bapi\b",
    "Oracle": r"\boracle\b",
    "Git": r"\bgit\b|github|gitlab",
    "English": r"ingilis|english",
    "Russian": r"\brus dili|\brus\b|russian",
}

CASE_SENSITIVE = {"R", "SAS", "DAX", "Machine learning"}

ROLE_FAMILIES = [
    ("Data Science / AI", r"data elmi|data science|scientist|\bai\b|machine learning|model"),
    ("Data Engineering / Governance", r"engineer|arxitekt|idarəçiliyi|data risk"),
    ("Business Analyst", r"biznes analitik|business analyst|biznes analitika"),
    ("Data Analyst", r"data analitik|data analyst|data analitika|məlumat bazası|analitik"),
    ("Reporting / Financial Analyst", r"hesabat|reporting|investment|büdcə"),
]

SENIORITY = [
    ("Intern", r"təcrübə proqram|intern|təcrübəçi"),
    ("Lead / Head", r"rəhbər|müdir|head|lead|menecer"),
    ("Senior", r"senior|baş |böyük|aparıcı|ekspert|expert"),
    ("Junior / Mid", r".*"),
]


def is_data_role(title: str) -> bool:
    return bool(re.search(DATA_ROLE_PATTERN, title, re.I)) and not re.search(EXCLUDE_PATTERN, title, re.I)


def first_match(text: str, rules: list[tuple[str, str]], default: str = "Other") -> str:
    for label, pattern in rules:
        if re.search(pattern, text, re.I):
            return label
    return default


def extract_skills(text: str) -> dict[str, bool]:
    result = {}
    for skill, pattern in SKILLS.items():
        flags = 0 if skill in CASE_SENSITIVE else re.I
        result[skill] = bool(re.search(pattern, text, flags))
    return result


def min_experience_years(text: str) -> float | None:
    after = re.findall(r"(\d{1,2})\s*(?:[-–]\s*\d{1,2}\s*)?(?:il|illik)\b[^.;]{0,25}təcrübə", text, re.I)
    before = re.findall(r"təcrübə[^.;\d]{0,30}?(\d{1,2})\s*(?:[-–]\s*\d{1,2}\s*)?(?:il|illik)\b", text, re.I)
    matches = after + before
    years = [int(m) for m in matches if int(m) <= 15]
    return min(years) if years else None


def salary_disclosed(salary_raw: str) -> bool:
    return bool(re.search(r"\d", salary_raw or ""))


def build_features(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw[raw["title"].apply(is_data_role)].copy()
    text = df["title"] + " " + df["description"]
    df["role_family"] = df["title"].apply(lambda t: first_match(t, ROLE_FAMILIES))
    df["seniority"] = df["title"].apply(lambda t: first_match(t, SENIORITY))
    df["min_experience_years"] = text.apply(min_experience_years)
    df["salary_disclosed"] = df["salary_raw"].apply(salary_disclosed)
    skills = pd.DataFrame(text.apply(extract_skills).tolist(), index=df.index)
    df["id"] = df["slug"].str.strip()
    columns = ["id", "title", "company", "date_posted", "valid_through", "city",
               "role_family", "seniority", "min_experience_years", "salary_disclosed"]
    return pd.concat([df[columns], skills], axis=1).reset_index(drop=True)
