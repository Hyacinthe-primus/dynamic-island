"""Saisie rapide en français : « Réunion demain 14h30 », « Appeler Paul lundi !haute #travail »,
« Anniversaire Marie 12/03 », « Dentiste le 5 à 9h pendant 30min »."""
import datetime as dt
import re

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
JOURS_COURTS = ["lun", "mar", "mer", "jeu", "ven", "sam", "dim"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]

PRIO = {"!haute": 3, "!élevée": 3, "!elevee": 3, "!urgent": 3, "!!!": 3,
        "!moyenne": 2, "!!": 2, "!faible": 1, "!basse": 1, "!": 1}


def parse(text, now=None):
    """Renvoie dict(title, date, time, duration_min, priority, project, birthday)."""
    now = now or dt.datetime.now()
    s = " " + text.strip() + " "
    out = {"date": None, "time": None, "duration": None, "priority": 0, "project": None, "birthday": False}

    def cut(m):
        nonlocal s
        s = s[:m.start()] + " " + s[m.end():]

    # priorité
    for tok, val in sorted(PRIO.items(), key=lambda kv: -len(kv[0])):
        m = re.search(r"(?<!\S)" + re.escape(tok) + r"(?!\S)", s, re.I)
        if m:
            out["priority"] = val
            cut(m)
            break
    # projet
    m = re.search(r"(?<!\S)#([\w-]+)", s)
    if m:
        out["project"] = m.group(1)
        cut(m)
    # anniversaire
    if re.search(r"\b(anniv(ersaire)?|birthday)\b", s, re.I):
        out["birthday"] = True
    # durée
    m = re.search(r"\bpendant\s+(\d+)\s*(h|heures?|min|minutes?)\b", s, re.I)
    if m:
        n = int(m.group(1))
        out["duration"] = n * 60 if m.group(2).lower().startswith("h") else n
        cut(m)
    # heure
    m = re.search(r"\b(?:à\s+)?(\d{1,2})\s*(?:h|:)\s*(\d{2})?\b", s, re.I)
    if m and int(m.group(1)) < 24:
        out["time"] = dt.time(int(m.group(1)), int(m.group(2) or 0))
        cut(m)
    # date
    today = now.date()
    m = re.search(r"\b(aujourd'hui|auj|ce soir)\b", s, re.I)
    if m:
        out["date"] = today
        if m.group(1).lower() == "ce soir" and not out["time"]:
            out["time"] = dt.time(20, 0)
        cut(m)
    if not out["date"]:
        m = re.search(r"\baprès[- ]demain\b", s, re.I)
        if m:
            out["date"] = today + dt.timedelta(days=2)
            cut(m)
    if not out["date"]:
        m = re.search(r"\bdemain\b", s, re.I)
        if m:
            out["date"] = today + dt.timedelta(days=1)
            cut(m)
    if not out["date"]:
        m = re.search(r"\bdans\s+(\d+)\s*(jours?|j|semaines?)\b", s, re.I)
        if m:
            n = int(m.group(1)) * (7 if m.group(2).lower().startswith("s") else 1)
            out["date"] = today + dt.timedelta(days=n)
            cut(m)
    if not out["date"]:
        m = re.search(r"\b(?:le\s+)?(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?\b", s)
        if m:
            d, mo = int(m.group(1)), int(m.group(2))
            y = int(m.group(3)) if m.group(3) else today.year
            if y < 100:
                y += 2000
            try:
                date = dt.date(y, mo, d)
                if not m.group(3) and date < today:
                    date = date.replace(year=y + 1)
                out["date"] = date
                cut(m)
            except ValueError:
                pass
    if not out["date"]:
        m = re.search(r"\b(?:le\s+)?(\d{1,2})\s+(" + "|".join(MOIS) + r")\b", s, re.I)
        if m:
            try:
                date = dt.date(today.year, MOIS.index(m.group(2).lower()) + 1, int(m.group(1)))
                if date < today:
                    date = date.replace(year=today.year + 1)
                out["date"] = date
                cut(m)
            except ValueError:
                pass
    if not out["date"]:
        m = re.search(r"\b(?:ce\s+|prochain\s+)?(" + "|".join(JOURS) + r")(?:\s+prochain)?\b", s, re.I)
        if m:
            wd = JOURS.index(m.group(1).lower())
            delta = (wd - today.weekday()) % 7 or 7
            out["date"] = today + dt.timedelta(days=delta)
            cut(m)
    if not out["date"]:
        m = re.search(r"\ble\s+(\d{1,2})\b", s, re.I)
        if m:
            d = int(m.group(1))
            try:
                date = today.replace(day=d)
                if date < today:
                    date = (today.replace(day=1) + dt.timedelta(days=32)).replace(day=d)
                out["date"] = date
                cut(m)
            except ValueError:
                pass
    if out["time"] and not out["date"]:
        out["date"] = today if dt.datetime.combine(today, out["time"]) > now else today + dt.timedelta(days=1)

    title = re.sub(r"\s+", " ", s).strip(" ,-")
    title = re.sub(r"\b(le|à|pour)$", "", title).strip()
    out["title"] = title[:1].upper() + title[1:] if title else ""
    return out


def parse_duration(text):
    """'25', '10m', '1h30', '90s', '1:30' -> secondes (None si invalide)."""
    t = text.strip().lower().replace(" ", "")
    if not t:
        return None
    m = re.fullmatch(r"(\d+)(?:s|sec|secondes?)", t)
    if m:
        return int(m.group(1)) or None
    m = re.fullmatch(r"(\d+):(\d{1,2})(?::(\d{1,2}))?", t)
    if m:
        a, b, c = m.groups()
        return int(a) * 3600 + int(b) * 60 + int(c) if c else int(a) * 60 + int(b)
    m = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)(?:m|min)?)?(?:(\d+)s)?", t)
    if m and any(m.groups()):
        h, mi, s = (int(x) if x else 0 for x in m.groups())
        total = h * 3600 + mi * 60 + s
        return total or None
    return None
