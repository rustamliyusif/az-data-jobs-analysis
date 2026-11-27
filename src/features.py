import re

import pandas as pd

IT_ROLE_PATTERN = (
    r"\bit\b|data|analitik|analyst|analitika|məlumat bazası|reporting|scientist|\bmodel"
    r"|developer|proqramçı|proqramist|proqramlaşdır|proqram təminatı|tərtibatçı|software|programmer"
    r"|backend|back-end|frontend|front-end|full[\s-]?stack|\bmobil|android|\bios\b|flutter"
    r"|devops|\bsre\b|cloud|bulud|sistem administrator|system administrator|sistem inzibatçı|şəbəkə|network"
    r"|kiber|cyber|informasiya təhlükəsizliyi|information security|\bsoc\b|pentest"
    r"|\bqa\b|tester|test mühəndisi|testləşdirmə|quality assurance"
    r"|ui/ux|\bux\b|\bui\b|product designer|web dizayner|veb dizayner"
    r"|product owner|product manager|məhsul meneceri|məhsul sahibi|scrum master|delivery manager"
    r"|\b1c\b|\bsap\b|\berp\b|\bcrm\b|texniki dəstək|help ?desk|technical support|service desk"
    r"|\.net|\bjava\b|python|\bphp\b|javascript|react|\bc#|golang|kotlin|swift|odoo|bitrix"
    r"|\bai\b|\baİ\b|süni intellekt|machine learning"
)
IT_CATEGORY_PATTERN = (r"Texnologiya|Veb[ -]dizayn|UI/UX|İnformasiya texnologiyaları|Proqramlaşdırma|Sistem idarəetməsi"
                       r"|\bİT mütəxəssisi|\bİT layihələrin|Məlumat bazasının|Texniki avadanlıq|Proqram təminatı"
                       r"|IT Helpdesk|1C inzibatçısı|Məlumat analitikası|application developer|Kibertəhlükəsizlik")
EXCLUDE_PATTERN = (r"^satış|kredit|lombard|marketinq|marketing|smm|sürücü|anbar|mühasib|hüquq|\bmep\b|qa/qc|usta|kassir|tikinti|smeta|hovuz|havalandırma|mexanik|lokomotiv|avtoelektrik|konsolidasiya"
                   r"|mobiloqraf|mobilqraf|reels|videoqraf|video creator|сотрудник бара|laborator|investisiya|financial"
                   r"|maliyyə və kommersiya|mağaza|stomatoloq|stomatoloji|korporativ satış|ofis inzibatçı|qeydiyyat üzrə")

SKILLS = {
    "SQL": r"\bsql\b|t-sql|pl/sql",
    "Excel": r"\bexcel\b",
    "Power BI": r"power\s?bi",
    "Tableau": r"\btableau\b",
    "Python": r"\bpython\b",
    "R": r"\bR\b(?=[\s,/)])",
    "Java": r"\bjava\b(?!\s?script)",
    "C# / .NET": r"\bc#|\.net\b|asp\.net|dotnet",
    "PHP": r"\bphp\b|laravel",
    "JavaScript": r"javascript|\bjs\b",
    "TypeScript": r"typescript",
    "React": r"\breact\b|react\.js|reactjs",
    "Angular": r"\bangular",
    "Vue": r"\bvue",
    "Node.js": r"node\.?js",
    "Go": r"\bgolang\b|\bGo\b(?=[\s,/)])",
    "Kotlin": r"\bkotlin\b",
    "Swift": r"\bswift\b",
    "Flutter": r"\bflutter\b|\bdart\b",
    "Django / FastAPI": r"\bdjango\b|fastapi|\bflask\b",
    "Spring": r"\bspring\b",
    "HTML / CSS": r"\bhtml|\bcss\b",
    "PostgreSQL": r"postgre",
    "MS SQL Server": r"ms\s?sql|sql server",
    "Oracle": r"\boracle\b",
    "MongoDB / NoSQL": r"mongo|nosql|redis",
    "Docker": r"\bdocker\b",
    "Kubernetes": r"kubernetes|\bk8s\b|openshift",
    "CI/CD": r"ci/cd|jenkins|gitlab ci|github actions",
    "AWS": r"\baws\b|amazon web services",
    "Azure": r"\bazure\b",
    "Linux": r"\blinux\b|ubuntu|centos|red hat|rhel",
    "Windows Server / AD": r"windows server|active directory",
    "Networking": r"\bcisco\b|ccna|ccnp|tcp/ip|\blan\b|\bwan\b|vpn|firewall|fortigate|mikrotik",
    "Cybersecurity": r"\bsiem\b|\bsoc\b|pentest|iso\s?27001|kibertəhlükəsizlik|cyber ?security",
    "Git": r"\bgit\b|github|gitlab",
    "REST API": r"\bapi\b|\brest\b|restful",
    "Microservices": r"mikroservis|microservice",
    "Selenium / Test automation": r"selenium|cypress|playwright|test avtomatlaşdırma|test automation",
    "Figma": r"\bfigma\b",
    "ETL": r"\betl\b|\bssis\b",
    "Data warehouse": r"\bdwh\b|data warehouse",
    "Statistics": r"statisti",
    "Machine learning": r"machine learning|maşın öyrənmə|\bML\b",
    "LLM / GenAI": r"\bllm|genai|generativ",
    "1C": r"\b1c\b|1с",
    "SAP / ERP": r"\bsap\b|\berp\b|odoo",
    "BPMN / UML": r"\bbpmn\b|\buml\b",
    "Jira / Confluence": r"\bjira\b|confluence",
    "Agile / Scrum": r"\bagile\b|\bscrum\b|kanban",
    "English": r"ingilis|english",
    "Russian": r"\brus dili|\brus\b|russian",
}

CASE_SENSITIVE = {"R", "Go", "Machine learning"}

ROLE_FAMILIES = [
    ("Cybersecurity", r"\bit risk|\bİT risk|təhlükəsizlik|kiber|cyber|informasiya təhlükəsizliyi|information security|\bsoc\b|pentest|security"),
    ("QA / Testing", r"\btest |\bqa\b|\bsdet\b|tester|test mühəndisi|testləşdirmə|quality assurance"),
    ("DevOps / Cloud", r"devops|\bsre\b|cloud|bulud|platform engineer|infrastructure engineer"),
    ("Data Engineering / Governance", r"data engineer|data mühəndis|data arxitekt|data architect|idarəçiliyi|data risk|\betl\b|dwh"),
    ("Data Science / AI", r"data elmi|data science|scientist|\bai\b|\baİ\b|machine learning|süni intellekt|\bmodel"),
    ("Business Analyst", r"biznes analitik|business analyst|biznes analitika|sistem analitik|system analyst"),
    ("Reporting / Financial Analyst", r"hesabat|reporting|investment|büdcə"),
    ("Data Analyst", r"data mütəxəssis|data analitik|data analyst|data analitika|məlumat bazası|analitik|analyst"),
    ("ERP / 1C / CRM", r"\b1c\b|\b1с|\bsap\b|\berp\b|\bcrm\b|odoo|bitrix"),
    ("Mobile Developer", r"\bmobil.*(developer|proqramçı|tərtibatçı)|android|\bios\b|flutter|kotlin|swift"),
    ("Frontend Developer", r"frontend|front-end|react|angular|\bvue"),
    ("Full-stack Developer", r"full[\s-]?stack"),
    ("Backend Developer", r"backend|back-end|\.net|\bjava\b|python|\bphp\b|golang|\bnode"),
    ("Software Developer", r"developer|proqramçı|proqramist|proqramlaşdır|tərtibatçı|software|programmer|proqram təminatı"),
    ("UI/UX Design", r"ui/ux|\bux\b|\bui\b|product designer|web dizayner|veb dizayner"),
    ("System / Network Admin", r"database administrator|\bdba\b|sistemlərinin idarə|voip|asterisk|infrastruktur|sistem inzibatçı|sistem idarə|sistem administrator|system administrator|şəbəkə|network|sistem mühəndisi|system engineer"),
    ("IT Support / Hardware", r"texnik|zəif axın|cctv|avadanlıq|компьют|ремонт|texniki dəstək|help ?desk|technical support|service desk|elektronika|\bit support|\bit mütəxəssis|\bit üzrə|\bit coordinator|informasiya texnologiyaları üzrə|\bit specialist"),
    ("Product / Project", r"product owner|product manager|məhsul meneceri|məhsul sahibi|scrum master|delivery manager|layihə|project"),
]

SENIORITY = [
    ("Intern", r"təcrübə proqram|intern|təcrübəçi"),
    ("Lead / Head", r"rəhbər|müdir|head|lead|menecer"),
    ("Senior", r"senior|baş |böyük|aparıcı|ekspert|expert"),
    ("Junior / Mid", r".*"),
]


def is_it_role(title: str, category: str = "") -> bool:
    if re.search(EXCLUDE_PATTERN, title, re.I):
        return False
    return bool(re.search(IT_CATEGORY_PATTERN, category or "", re.I)) or bool(re.search(IT_ROLE_PATTERN, title, re.I))


def first_match(text: str, rules: list[tuple[str, str]], default: str = "Other IT") -> str:
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
    years = [int(m) for m in after + before if int(m) <= 15]
    return min(years) if years else None


WORK_FORMATS = [
    ("Remote", r"\bremote\b|uzaqdan|distansion|onlayn iş|tam uzaqdan|work from home"),
    ("Hibrid", r"hibrid|hybrid"),
]


def work_format(text: str) -> str:
    return first_match(text, WORK_FORMATS, default="Ofis")


def salary_disclosed(salary_raw: str) -> bool:
    return bool(re.search(r"\d", salary_raw or ""))


def parse_salary(salary_raw: str) -> tuple[float | None, float | None]:
    numbers = [float(n.replace(" ", "")) for n in re.findall(r"\d[\d ]*\d|\d", salary_raw or "")]
    numbers = [n for n in numbers if 100 <= n <= 50000]
    if not numbers:
        return None, None
    return min(numbers), max(numbers)


def build_features(raw: pd.DataFrame) -> pd.DataFrame:
    raw = raw.assign(category=raw["category"].fillna("") if "category" in raw else "")
    df = raw[[is_it_role(t, c) for t, c in zip(raw["title"], raw["category"])]].copy()
    text = df["title"] + " " + df["description"]
    df["role_family"] = df["title"].apply(lambda t: first_match(t, ROLE_FAMILIES))
    df["seniority"] = df["title"].apply(lambda t: first_match(t, SENIORITY))
    df["min_experience_years"] = text.apply(min_experience_years)
    df["work_format"] = text.apply(work_format)
    df["salary_disclosed"] = df["salary_raw"].apply(salary_disclosed)
    parsed = df["salary_raw"].apply(parse_salary)
    df["salary_from"] = df["salary_from"] if "salary_from" in df else parsed.str[0]
    df["salary_to"] = df["salary_to"] if "salary_to" in df else parsed.str[1]
    df["salary_from"] = pd.to_numeric(df["salary_from"], errors="coerce").fillna(parsed.str[0])
    df["salary_to"] = pd.to_numeric(df["salary_to"], errors="coerce").fillna(parsed.str[1])
    skills = pd.DataFrame(text.apply(extract_skills).tolist(), index=df.index)
    df["id"] = df["slug"].str.strip()
    df["category"] = df["category"].str.replace(r"^Ana səhifə > Vakansiyalar > ", "", regex=True)
    columns = ["id", "title", "company", "category", "date_posted", "valid_through", "city",
               "role_family", "seniority", "min_experience_years", "work_format", "salary_disclosed", "salary_from", "salary_to"]
    return pd.concat([df[columns], skills], axis=1).reset_index(drop=True)


LEGAL_SUFFIX = r"\b(asc|qsc|mmc|llc|ojsc|cjsc|ltd|llp|inc|jsc|şirkəti|şirkət|company|group|azerbaijan|azərbaycan)\b"
AZ_TRANSLIT = str.maketrans("əğıöüşçƏĞIİÖÜŞÇ", "egiouscegiiousc")


def normalize(text: str) -> str:
    text = (text or "").translate(AZ_TRANSLIT).lower().replace("sh", "s").replace("ch", "c")
    text = re.sub(LEGAL_SUFFIX, " ", text)
    return re.sub(r"[^a-z0-9а-я]+", "", text)


def duplicate_key(title: str, company: str) -> str:
    company_key = normalize(company)
    title_key = normalize(title).replace(company_key, "") if company_key else normalize(title)
    return f"{company_key}|{title_key}"
