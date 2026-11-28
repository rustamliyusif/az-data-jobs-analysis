import argparse
import json
import os
import re
import statistics
from datetime import date
from html import escape
from pathlib import Path

import pandas as pd
import requests
from cryptography.fernet import Fernet

from features import ROLE_FAMILIES, SKILLS, extract_skills, first_match
from notify_telegram import DASHBOARD, new_vacancies, salary_text, vacancy_url

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "data" / "bot_state.enc"
SURVEY_PATH = ROOT / "data" / "processed" / "salary_survey.csv"
BOT_INFO_PATH = ROOT / "data" / "processed" / "bot.json"
MIN_GROUP = 5
MATCH_SHARE = 0.5
MAX_DIGEST = 15
LEVELS = [
    ("Intern", r"intern|təcrübəçi|stajyor|стаж"),
    ("Junior", r"junior|kiçik|джун"),
    ("Middle", r"middle|mid\b|orta|мидл"),
    ("Senior", r"senior|böyük|baş|aparıcı|сеньор"),
    ("Lead", r"lead|head|rəhbər|müdir|лид"),
]

HELP = (
    "👋 <b>AZ IT Jobs botu</b>\n\n"
    "Hər səhər hellojob.az, busy.az və boss.az-da çıxan yeni IT vakansiyalarından "
    "yalnız sənin bacarıqlarına uyğun olanları göndərirəm.\n\n"
    "<b>Bacarıqlarını yaz:</b>\n"
    "<code>/skills SQL, Python, Power BI, English</code>\n\n"
    "<b>Digər əmrlər:</b>\n"
    "/junior — yalnız junior və təcrübə vakansiyaları (yenidən yazsan söndürülür)\n"
    "/status — seçdiklərini göstərir\n"
    "/stop — bildirişləri dayandırır\n"
    "/maas — maaşını anonim paylaş, bazar statistikasına töhfə ver\n\n"
    f"📊 Sayt: {DASHBOARD}\n"
    "<i>Cavablar bir neçə dəqiqə gecikə bilər.</i>"
)

SALARY_HELP = (
    "💰 <b>Anonim maaş sorğusu</b>\n\n"
    "Bir mesajda rolunu, səviyyəni, təcrübəni (il) və aylıq <b>net</b> maaşını (AZN) vergüllə yaz:\n"
    "<code>/maas Data Analyst, Junior, 1, 1200</code>\n\n"
    "Səviyyə: Intern, Junior, Middle, Senior, Lead.\n"
    "Adın və hesabın heç yerdə saxlanmır və göstərilmir. Saytda yalnız ən azı "
    f"{MIN_GROUP} cavab olan qrupların median rəqəmləri görünür. Yenidən göndərsən, əvvəlki cavabın əvəz olunur.\n"
    "Cavabını silmək üçün: /maas_sil"
)


class Bot:
    def __init__(self, token: str):
        self.base = f"https://api.telegram.org/bot{token}"

    def call(self, method: str, **params) -> dict:
        response = requests.post(f"{self.base}/{method}", data=params, timeout=30)
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(f"{method} failed: {payload.get('description')}")
        return payload["result"]

    def send(self, chat_id: str, text: str) -> bool:
        try:
            self.call("sendMessage", chat_id=chat_id, text=text, parse_mode="HTML", disable_web_page_preview="true")
            return True
        except RuntimeError as error:
            print(f"  send to user failed: {error}")
            return "blocked" not in str(error) and "deactivated" not in str(error)


def load_state(key: bytes) -> dict:
    if not STATE_PATH.exists():
        return {"offset": 0, "users": {}, "salaries": {}}
    return json.loads(Fernet(key).decrypt(STATE_PATH.read_bytes()))


def save_state(state: dict, key: bytes) -> None:
    STATE_PATH.write_bytes(Fernet(key).encrypt(json.dumps(state, ensure_ascii=False).encode()))


def parse_skills(text: str) -> list[str]:
    found = extract_skills(text)
    return [skill for skill, present in found.items() if present]


def parse_salary(text: str) -> dict | None:
    parts = [p.strip() for p in text.split(",")]
    if len(parts) < 4:
        return None
    role = first_match(parts[0], ROLE_FAMILIES, default="")
    level = first_match(parts[1], LEVELS, default="")
    years = re.search(r"\d+(?:[.,]\d+)?", parts[2])
    salary = re.search(r"\d[\d\s]*", parts[3])
    if not role or not level or not years or not salary:
        return None
    amount = int(re.sub(r"\s", "", salary.group(0)))
    years_value = float(years.group(0).replace(",", "."))
    if not 200 <= amount <= 30000 or not 0 <= years_value <= 40:
        return None
    return {"role": role, "level": level, "years": years_value, "salary": amount, "date": date.today().isoformat()}


def handle(bot: Bot, state: dict, chat_id: str, text: str) -> None:
    command, _, rest = text.strip().partition(" ")
    command = command.split("@")[0].lower()
    user = state["users"].setdefault(chat_id, {"skills": [], "junior": False, "active": False})

    if command in ("/start", "/help", "/kömək"):
        bot.send(chat_id, HELP)
    elif command in ("/skills", "/bacariqlar", "/bacarıqlar"):
        skills = parse_skills(rest)
        if not skills:
            bot.send(chat_id, "Bacarıq tanımadım. Nümunə: <code>/skills SQL, Python, Power BI, English</code>\n"
                              f"Tanıdığım bacarıqlar: {escape(', '.join(SKILLS))}")
            return
        user.update(skills=skills, active=True)
        bot.send(chat_id, f"✅ Yadda saxladım: <b>{escape(', '.join(skills))}</b>\n"
                          "Hər səhər bu bacarıqların ən azı yarısını tələb edən yeni vakansiyaları göndərəcəyəm.")
    elif command == "/junior":
        user["junior"] = not user.get("junior", False)
        bot.send(chat_id, "🎓 Yalnız junior və təcrübə vakansiyalarını göndərəcəyəm." if user["junior"]
                 else "Bütün səviyyələrdən vakansiyaları göndərəcəyəm.")
    elif command == "/status":
        skills = ", ".join(user.get("skills", [])) or "seçilməyib"
        bot.send(chat_id, f"Bacarıqlar: <b>{escape(skills)}</b>\n"
                          f"Bildirişlər: {'açıq' if user.get('active') else 'bağlı'}\n"
                          f"Yalnız junior: {'bəli' if user.get('junior') else 'xeyr'}\n"
                          f"Maaş cavabın: {'var' if chat_id in state['salaries'] else 'yoxdur'}")
    elif command == "/stop":
        user["active"] = False
        bot.send(chat_id, "Bildirişləri dayandırdım. Yenidən başlamaq üçün bacarıqlarını /skills ilə yaz.")
    elif command in ("/maas", "/maaş"):
        if not rest.strip():
            bot.send(chat_id, SALARY_HELP)
            return
        entry = parse_salary(rest)
        if entry is None:
            bot.send(chat_id, "Formatı tanımadım. Nümunə: <code>/maas Data Analyst, Junior, 1, 1200</code>\n"
                              "Rol, səviyyə, təcrübə (il), aylıq net maaş (200–30000 AZN).")
            return
        state["salaries"][chat_id] = entry
        bot.send(chat_id, f"🙏 Təşəkkürlər! Qeyd etdim: {escape(entry['role'])}, {entry['level']}, "
                          f"{entry['years']:g} il, {entry['salary']} ₼.\nCavabını silmək üçün: /maas_sil")
    elif command in ("/maas_sil", "/maaş_sil"):
        removed = state["salaries"].pop(chat_id, None)
        bot.send(chat_id, "Maaş cavabını sildim." if removed else "Səndən maaş cavabı yoxdur.")
    else:
        bot.send(chat_id, HELP)


def write_survey(state: dict) -> None:
    rows = pd.DataFrame(state["salaries"].values())
    groups = []
    if not rows.empty:
        for keys, frame in [(("Bütün rollar", "Hamısı"), rows)] + \
                           [((r, "Hamısı"), f) for r, f in rows.groupby("role")] + \
                           [((r, l), f) for (r, l), f in rows.groupby(["role", "level"])]:
            if len(frame) >= MIN_GROUP:
                values = sorted(frame["salary"])
                quartiles = statistics.quantiles(values, n=4) if len(values) > 1 else [values[0]] * 3
                groups.append({"role": keys[0], "level": keys[1], "n": len(values), "median": statistics.median(values),
                               "p25": quartiles[0], "p75": quartiles[2]})
    SURVEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(groups, columns=["role", "level", "n", "median", "p25", "p75"]).to_csv(SURVEY_PATH, index=False)
    print(f"Survey: {len(rows)} answers, {len(groups)} published groups")


def poll(bot: Bot, state: dict) -> None:
    updates = bot.call("getUpdates", offset=state["offset"], timeout=0, allowed_updates='["message"]')
    for update in updates:
        state["offset"] = update["update_id"] + 1
        message = update.get("message") or {}
        chat = message.get("chat") or {}
        text = message.get("text")
        if chat.get("type") != "private" or not text:
            continue
        handle(bot, state, str(chat["id"]), text)
    print(f"Processed {len(updates)} updates, {sum(u.get('active', False) for u in state['users'].values())} active subscribers")


def coverage(row: pd.Series, skills: list[str]) -> float:
    required = [s for s in SKILLS if bool(row.get(s))]
    if not required:
        return 0.0
    return sum(s in skills for s in required) / len(required)


def digest(bot: Bot, state: dict) -> None:
    day, rows = new_vacancies()
    if rows.empty:
        print("No new vacancies, no digests")
        return
    skill_columns = [c for c in SKILLS if c in rows]
    rows = rows.assign(**{c: rows[c].fillna(False).astype(bool) for c in skill_columns})
    junior_title = rows["title"].str.contains(r"junior|intern|trainee|təcrübəçi|təcrübə proqram|kiçik", case=False, regex=True)
    junior = junior_title | (rows["seniority"] == "Intern") | (rows["min_experience_years"] <= 1)
    sent = 0
    for chat_id, user in state["users"].items():
        if not user.get("active") or not user.get("skills"):
            continue
        pool = rows[junior] if user.get("junior") else rows
        if pool.empty:
            continue
        pool = pool.assign(score=[coverage(r, user["skills"]) for _, r in pool.iterrows()])
        matches = pool[pool["score"] >= MATCH_SHARE].sort_values("score", ascending=False)
        if matches.empty:
            continue
        day_text = pd.Timestamp(day).strftime("%d.%m.%Y")
        lines = [f"• <a href=\"{vacancy_url(r)}\">{escape(r['title'])}</a> — {escape(str(r['company']))}"
                 f"{salary_text(r)} · {r['score'] * 100:.0f}% uyğun" for _, r in matches.head(MAX_DIGEST).iterrows()]
        more = f"\n…və daha {len(matches) - MAX_DIGEST} vakansiya." if len(matches) > MAX_DIGEST else ""
        text = (f"🎯 <b>Sənə uyğun yeni vakansiyalar — {day_text}</b> ({len(matches)})\n\n" + "\n".join(lines) + more +
                f"\n\n📊 {DASHBOARD}\nBacarıqları dəyişmək: /skills · dayandırmaq: /stop")
        if bot.send(chat_id, text):
            sent += 1
        else:
            user["active"] = False
    print(f"Digests sent: {sent}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Personal Telegram alerts and anonymous salary survey")
    parser.add_argument("mode", choices=["poll", "digest"])
    args = parser.parse_args()
    token, key = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("BOT_STATE_KEY")
    if not token or not key:
        raise SystemExit("TELEGRAM_BOT_TOKEN and BOT_STATE_KEY must be set")
    bot = Bot(token)
    state = load_state(key.encode())
    before = json.dumps(state, sort_keys=True)
    if args.mode == "poll":
        username = bot.call("getMe").get("username", "")
        BOT_INFO_PATH.write_text(json.dumps({"username": username}))
        poll(bot, state)
        write_survey(state)
    else:
        digest(bot, state)
    if json.dumps(state, sort_keys=True) != before or not STATE_PATH.exists():
        save_state(state, key.encode())
        print("State updated")


if __name__ == "__main__":
    main()
