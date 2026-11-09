"""Minuteurs multiples, chronomètre, Pomodoro (avec pauses), alarmes,
historique des sessions de travail, statistiques et mode concentration."""
import datetime as dt
import os
import time
import uuid
import winsound

from PySide6.QtCore import QObject, Signal

from store import Collection, settings

SOUND_TIMER = r"C:\Windows\Media\Alarm01.wav"
SOUND_ALARM = r"C:\Windows\Media\Alarm03.wav"
SOUND_SOFT = r"C:\Windows\Media\Windows Notify Calendar.wav"


def play(path):
    try:
        if os.path.exists(path):
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        else:
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
    except Exception:
        pass


class Timers(QObject):
    fired = Signal(str, str, str)   # kind, titre, sous-titre
    focus_changed = Signal(bool)

    def __init__(self):
        super().__init__()
        self.timers = []       # comptes à rebours
        self.stopwatch = {"running": False, "start": 0.0, "acc": 0.0, "laps": []}
        cfg = settings.get("pomodoro", {})
        self.pomo_cfg = {"work": cfg.get("work", 25), "short": cfg.get("short", 5),
                         "long": cfg.get("long", 15), "every": cfg.get("every", 4),
                         "auto": cfg.get("auto", True)}
        self.pomo = {"phase": "work", "running": False, "end": 0.0, "remaining": self.pomo_cfg["work"] * 60,
                     "cycles": 0, "label": "Concentration", "started": None}
        self.focus = False
        self.alarms = Collection("alarms")
        self.sessions = Collection("sessions")
        self._alarm_fired = set()

    # ---------------------------------------------------------------- comptes à rebours
    def add_timer(self, seconds, label=None):
        t = {"id": uuid.uuid4().hex, "label": label or self._label(seconds), "duration": seconds,
             "end": time.time() + seconds, "remaining": seconds, "running": True, "started": time.time()}
        self.timers.append(t)
        return t

    @staticmethod
    def _label(sec):
        if sec % 3600 == 0:
            return f"{sec // 3600} h"
        if sec >= 3600:
            return f"{sec // 3600} h {sec % 3600 // 60:02d}"
        if sec % 60 == 0:
            return f"{sec // 60} min"
        return f"{sec // 60} min {sec % 60:02d} s" if sec >= 60 else f"{sec} s"

    def remaining(self, t):
        return max(0.0, t["end"] - time.time()) if t["running"] else t["remaining"]

    def toggle_timer(self, t):
        if t["running"]:
            t["remaining"] = self.remaining(t)
            t["running"] = False
        else:
            if t["remaining"] <= 0:
                t["remaining"] = t["duration"]
            t["end"] = time.time() + t["remaining"]
            t["running"] = True

    def reset_timer(self, t):
        t["running"] = False
        t["remaining"] = t["duration"]

    def remove_timer(self, t):
        if t in self.timers:
            self.timers.remove(t)

    def add_time(self, t, seconds):
        if t["running"]:
            t["end"] += seconds
        else:
            t["remaining"] += seconds
        t["duration"] += seconds

    # ---------------------------------------------------------------- chronomètre
    def sw_elapsed(self):
        s = self.stopwatch
        return s["acc"] + (time.time() - s["start"] if s["running"] else 0)

    def sw_toggle(self):
        s = self.stopwatch
        if s["running"]:
            s["acc"] = self.sw_elapsed()
            s["running"] = False
        else:
            s["start"] = time.time()
            s["running"] = True

    def sw_lap(self):
        if self.stopwatch["running"]:
            self.stopwatch["laps"].insert(0, self.sw_elapsed())

    def sw_reset(self):
        self.stopwatch = {"running": False, "start": 0.0, "acc": 0.0, "laps": []}

    # ---------------------------------------------------------------- pomodoro
    def phase_len(self, phase=None):
        return self.pomo_cfg[phase or self.pomo["phase"]] * 60

    def pomo_remaining(self):
        p = self.pomo
        return max(0.0, p["end"] - time.time()) if p["running"] else p["remaining"]

    def pomo_toggle(self):
        p = self.pomo
        if p["running"]:
            p["remaining"] = self.pomo_remaining()
            p["running"] = False
        else:
            p["end"] = time.time() + p["remaining"]
            p["running"] = True
            if p["phase"] == "work" and p["started"] is None:
                p["started"] = time.time()

    def pomo_skip(self):
        self._pomo_next(log=False)

    def pomo_reset(self):
        self.pomo.update(phase="work", running=False, remaining=self.phase_len("work"), cycles=0, started=None)

    def set_pomo_cfg(self, **kw):
        self.pomo_cfg.update(kw)
        settings.set("pomodoro", self.pomo_cfg)
        if not self.pomo["running"]:
            self.pomo["remaining"] = self.phase_len()

    def _pomo_next(self, log=True):
        p = self.pomo
        if p["phase"] == "work":
            if log and p["started"]:
                self.log_session("pomodoro", p["started"], time.time(), p["label"])
            p["cycles"] += 1
            p["phase"] = "long" if p["cycles"] % self.pomo_cfg["every"] == 0 else "short"
        else:
            p["phase"] = "work"
        p["started"] = None
        p["remaining"] = self.phase_len()
        if self.pomo_cfg["auto"] and p["running"]:
            p["end"] = time.time() + p["remaining"]
            if p["phase"] == "work":
                p["started"] = time.time()
        else:
            p["running"] = False

    # ---------------------------------------------------------------- mode concentration
    def set_focus(self, on):
        if on == self.focus:
            return
        self.focus = on
        if on:
            self.pomo_reset()
            self.pomo_toggle()
        else:
            p = self.pomo
            if p["phase"] == "work" and p["started"] and time.time() - p["started"] > 60:
                self.log_session("pomodoro", p["started"], time.time(), p["label"])
            self.pomo_reset()
        self.focus_changed.emit(on)

    # ---------------------------------------------------------------- alarmes
    def add_alarm(self, hhmm, label="Alarme", days=None):
        return self.alarms.add(time=hhmm, label=label, days=days or [], enabled=True)

    def toggle_alarm(self, a):
        self.alarms.update(a, enabled=not a.get("enabled", True))

    def next_alarm(self):
        now = dt.datetime.now()
        best = None
        for a in self.alarms.items:
            if not a.get("enabled", True):
                continue
            h, m = map(int, a["time"].split(":"))
            for add in range(8):
                d = now.date() + dt.timedelta(days=add)
                when = dt.datetime.combine(d, dt.time(h, m))
                if when <= now or (a.get("days") and d.weekday() not in a["days"]):
                    continue
                if best is None or when < best[0]:
                    best = (when, a)
                break
        return best

    # ---------------------------------------------------------------- sessions / statistiques
    def log_session(self, kind, start, end, label=""):
        if end - start >= 30:
            self.sessions.add(kind=kind, start=start, end=end, duration=end - start, label=label)

    def stats(self):
        today = dt.date.today()
        days = [today - dt.timedelta(days=i) for i in range(6, -1, -1)]
        per_day = {d: 0.0 for d in days}
        count_today = 0
        for s in self.sessions.items:
            d = dt.date.fromtimestamp(s["start"])
            if d in per_day:
                per_day[d] += s["duration"] / 60
            if d == today:
                count_today += 1
        total_week = sum(per_day.values())
        streak = 0
        for d in reversed(days):
            if per_day[d] > 0:
                streak += 1
            else:
                break
        return {"days": days, "per_day": per_day, "today": per_day[today], "count_today": count_today,
                "week": total_week, "streak": streak}

    def recent_sessions(self, n=8):
        return sorted(self.sessions.items, key=lambda s: -s["start"])[:n]

    # ---------------------------------------------------------------- boucle
    def tick(self):
        now = time.time()
        for t in list(self.timers):
            if t["running"] and now >= t["end"]:
                t["running"] = False
                t["remaining"] = 0
                self.log_session("timer", t["started"], now, t["label"])
                play(SOUND_TIMER)
                self.fired.emit("timer", "Minuteur terminé", t["label"])
        p = self.pomo
        if p["running"] and now >= p["end"]:
            was = p["phase"]
            self._pomo_next()
            play(SOUND_SOFT)
            if was == "work":
                nxt = "Grande pause" if p["phase"] == "long" else "Petite pause"
                self.fired.emit("pomodoro", "Session terminée", f"{nxt} de {self.pomo_cfg[p['phase']]} min")
            else:
                self.fired.emit("pomodoro", "Fin de la pause", "Au travail !")
        n = dt.datetime.now()
        hhmm = n.strftime("%H:%M")
        for a in self.alarms.items:
            if not a.get("enabled", True) or a["time"] != hhmm:
                continue
            if a.get("days") and n.weekday() not in a["days"]:
                continue
            key = (a["id"], n.date(), hhmm)
            if key in self._alarm_fired:
                continue
            self._alarm_fired.add(key)
            play(SOUND_ALARM)
            self.fired.emit("alarm", a.get("label") or "Alarme", hhmm)
            if not a.get("days"):
                self.alarms.update(a, enabled=False)

    def active(self):
        """Minuteur à afficher dans la pilule : (label, restant, fraction) ou None."""
        p = self.pomo
        if p["running"]:
            rem = self.pomo_remaining()
            name = {"work": "Focus", "short": "Pause", "long": "Pause"}[p["phase"]]
            return name, rem, 1 - rem / max(1, self.phase_len()), "pomo"
        running = [t for t in self.timers if t["running"]]
        if running:
            t = min(running, key=self.remaining)
            rem = self.remaining(t)
            return t["label"], rem, 1 - rem / max(1, t["duration"]), "timer"
        if self.stopwatch["running"]:
            return "Chrono", self.sw_elapsed(), None, "sw"
        return None
