"""Point d'accès mobile Windows (partage de connexion) et appareils du réseau local.

- Point d'accès : marche / arrêt, nom, mot de passe, bande, appareils connectés (nom, IP, MAC).
- Blocage : Windows ne permet pas d'éjecter un appareil du point d'accès. Bloquer un appareil change donc
  le mot de passe et redémarre le point d'accès : l'appareil bloqué perd l'accès, les autres se reconnectent
  avec le nouveau mot de passe (affiché en QR code). S'il revient malgré tout, il est signalé.
- Réseau local : appareils présents sur le Wi-Fi actuel (adresse IP, MAC, nom). Lecture seule : le blocage
  sur un réseau dont on n'est que client se fait dans l'administration du routeur."""
import asyncio
import ipaddress
import re
import secrets
import socket
import string
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import psutil
from PySide6.QtCore import QObject, Signal

from store import settings

NOWIN = 0x08000000
STATUS_MSG = {
    1: "Erreur inconnue",
    2: "Aucun réseau mobile disponible",
    3: "La carte Wi-Fi ne peut pas créer le point d'accès (Wi-Fi Direct déjà utilisé par Lien avec Windows, "
       "le partage de proximité ou une projection, ou Wi-Fi désactivé)",
    4: "Délai de vérification dépassé",
    5: "Le fournisseur refuse le partage de connexion",
    6: "Opération déjà en cours",
    7: "Bluetooth désactivé",
    8: "Connexion Internet limitée : rien à partager",
}
BANDS = {0: "Automatique", 1: "2,4 GHz", 2: "5 GHz"}


def _run(*args):
    r = subprocess.run(list(args), capture_output=True, creationflags=NOWIN)
    for enc in ("utf-8", "cp850", "cp1252"):
        try:
            return r.stdout.decode(enc)
        except UnicodeDecodeError:
            continue
    return r.stdout.decode("utf-8", "replace")


def arp_table():
    """{ip: mac} des entrées dynamiques de la table ARP."""
    out = {}
    for line in _run("arp", "-a").splitlines():
        m = re.match(r"\s*(\d+\.\d+\.\d+\.\d+)\s+([0-9a-f]{2}(?:-[0-9a-f]{2}){5})\s+(\w+)", line, re.I)
        if m and m.group(2).lower() != "ff-ff-ff-ff-ff-ff" and not m.group(1).startswith(("224.", "239.", "255.")):
            out[m.group(1)] = m.group(2).lower().replace("-", ":")
    return out


def _mac_norm(mac):
    return mac.lower().replace("-", ":")


def random_password(n=12):
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


def wifi_qr_text(ssid, password):
    esc = lambda s: re.sub(r"([\\;,:\"])", r"\\\1", s)
    return f"WIFI:T:WPA;S:{esc(ssid)};P:{esc(password)};;"


class Hotspot(QObject):
    changed = Signal()
    alert = Signal(str, str, bool)

    def __init__(self):
        super().__init__()
        self.state = None          # "on" | "off" | "transition" | None (indisponible)
        self.ssid = ""
        self.password = ""
        self.band = 0
        self.max_clients = 8
        self.clients = []          # [{mac, name, ip, blocked}]
        self.error = None
        self.busy = False
        self.visible = False
        self.lan = []              # appareils du réseau local
        self.lan_scanning = False
        self.lan_info = {}
        self._wake = threading.Event()
        threading.Thread(target=self._loop, daemon=True).start()

    # ------------------------------------------------------------ WinRT
    @staticmethod
    def _manager():
        from winrt.windows.networking.connectivity import NetworkInformation
        from winrt.windows.networking.networkoperators import NetworkOperatorTetheringManager as M
        prof = NetworkInformation.get_internet_connection_profile()
        if prof is None:
            return None
        return M.create_from_connection_profile(prof)

    def _read(self):
        m = self._manager()
        if m is None:
            self.state, self.error = None, "Pas de connexion Internet à partager"
            return
        st = int(m.tethering_operational_state)
        self.state = {1: "on", 2: "off", 3: "transition"}.get(st)
        cfg = m.get_current_access_point_configuration()
        self.ssid, self.password, self.band = cfg.ssid, cfg.passphrase, int(cfg.band)
        self.max_clients = m.max_client_count
        blocked = set(settings.get("hotspot_blocked", []))
        clients = []
        if self.state == "on":
            arp = {_mac_norm(mac): ip for ip, mac in arp_table().items() if ip.startswith("192.168.137.")}
            for c in m.get_tethering_clients():
                mac = _mac_norm(c.mac_address)
                names = [h.display_name for h in c.host_names]
                ip = next((n for n in names if re.match(r"\d+\.\d+\.\d+\.\d+$", n)), None) or arp.get(mac)
                name = next((n for n in names if not re.match(r"[\d.:a-f]+$", n, re.I)), None)
                clients.append({"mac": mac, "name": name or "Appareil", "ip": ip, "blocked": mac in blocked})
            for c in clients:
                if c["blocked"]:
                    self.alert.emit("Appareil bloqué reconnecté", f"{c['name']} · {c['mac']}", False)
        self.clients = clients

    def _loop(self):
        while True:
            try:
                self._read()
            except Exception as e:
                self.state, self.error = None, f"Point d'accès indisponible ({type(e).__name__})"
            self.changed.emit()
            self._wake.wait(2 if self.visible else 20)
            self._wake.clear()

    def refresh(self):
        self._wake.set()

    def _async(self, coro_fn, done_msg=None):
        def work():
            self.busy = True
            self.changed.emit()
            try:
                asyncio.run(coro_fn())
                if done_msg:
                    self.alert.emit(done_msg[0], done_msg[1], True)
            except Exception as e:
                self.error = str(e)[:120]
                self.alert.emit("Point d'accès", self.error, False)
            self.busy = False
            try:
                self._read()
            except Exception:
                pass
            self.changed.emit()
        threading.Thread(target=work, daemon=True).start()

    async def _start(self):
        m = self._manager()
        r = await m.start_tethering_async()
        st = int(r.status)
        if st != 0:
            self.error = STATUS_MSG.get(st, f"Échec (code {st})")
            self.alert.emit("Point d'accès non démarré", self.error.split(" (")[0], False)
        else:
            self.error = None
            self.alert.emit("Point d'accès activé", self.ssid, True)

    async def _stop(self):
        m = self._manager()
        await m.stop_tethering_async()
        self.error = None

    def toggle(self):
        self._async(self._stop if self.state == "on" else self._start)

    def configure(self, ssid=None, password=None, band=None, restart=None):
        """Change nom / mot de passe / bande (8 caractères min.) ; redémarre si le point d'accès tournait."""
        async def run():
            m = self._manager()
            cfg = m.get_current_access_point_configuration()
            if ssid:
                cfg.ssid = ssid
            if password:
                cfg.passphrase = password
            if band is not None:
                cfg.band = band
            was_on = int(m.tethering_operational_state) == 1
            await m.configure_access_point_async(cfg)
            if (restart if restart is not None else was_on) and was_on:
                await m.stop_tethering_async()
                await asyncio.sleep(1)
                await m.start_tethering_async()
        self._async(run, ("Point d'accès modifié", ssid or self.ssid))

    def block(self, client):
        """Bloque un appareil : nouveau mot de passe + redémarrage (Windows ne sait pas éjecter un appareil)."""
        blocked = set(settings.get("hotspot_blocked", []))
        blocked.add(client["mac"])
        names = dict(settings.get("hotspot_blocked_names", {}))
        names[client["mac"]] = client["name"]
        settings.set("hotspot_blocked", sorted(blocked))
        settings.set("hotspot_blocked_names", names)
        self.configure(password=random_password(), restart=True)
        self.alert.emit("Appareil bloqué", f"{client['name']} — nouveau mot de passe à partager", True)

    def unblock(self, mac):
        settings.set("hotspot_blocked", [m for m in settings.get("hotspot_blocked", []) if m != mac])
        self.changed.emit()

    @property
    def blocked(self):
        names = settings.get("hotspot_blocked_names", {})
        return [{"mac": m, "name": names.get(m, "Appareil")} for m in settings.get("hotspot_blocked", [])]

    # ------------------------------------------------------------ réseau local
    def scan_lan(self):
        if self.lan_scanning:
            return

        def work():
            self.lan_scanning = True
            self.changed.emit()
            try:
                self.lan = self._scan_lan()
            except Exception as e:
                self.lan_info["error"] = str(e)[:80]
            self.lan_scanning = False
            self.changed.emit()
        threading.Thread(target=work, daemon=True).start()

    def _scan_lan(self):
        # interface actuelle : celle qui sort vers Internet
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            my_ip = s.getsockname()[0]
        finally:
            s.close()
        mask = "255.255.255.0"
        my_mac = None
        for name, addrs in psutil.net_if_addrs().items():
            if any(a.address == my_ip for a in addrs):
                mask = next((a.netmask for a in addrs if a.address == my_ip), mask)
                my_mac = next((a.address for a in addrs if a.family == psutil.AF_LINK), None)
        net = ipaddress.ip_network(f"{my_ip}/{mask}", strict=False)
        if net.num_addresses > 1024:  # grands réseaux : on se limite au /24 autour de nous
            net = ipaddress.ip_network(f"{my_ip}/24", strict=False)
        gw = None
        for line in _run("route", "print", "-4", "0.0.0.0").splitlines():
            m = re.match(r"\s*0\.0\.0\.0\s+0\.0\.0\.0\s+(\d+\.\d+\.\d+\.\d+)\s+(\d+\.\d+\.\d+\.\d+)", line)
            if m and m.group(2) == my_ip:
                gw = m.group(1)
                break
        self.lan_info = {"ip": my_ip, "net": str(net), "gateway": gw}
        # réveille la table ARP : un petit paquet UDP vers chaque adresse
        u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        for host in net.hosts():
            try:
                u.sendto(b"\x00", (str(host), 9))
            except OSError:
                pass
        u.close()
        time.sleep(2.0)
        arp = {ip: mac for ip, mac in arp_table().items() if ipaddress.ip_address(ip) in net}
        arp[my_ip] = _mac_norm(my_mac) if my_mac else ""

        def name_of(ip):
            if ip == my_ip:
                return socket.gethostname()
            try:
                return socket.gethostbyaddr(ip)[0].split(".")[0]
            except OSError:
                return None
        with ThreadPoolExecutor(32) as ex:
            names = dict(zip(arp, ex.map(name_of, arp)))
        devices = []
        for ip, mac in arp.items():
            kind = "self" if ip == my_ip else ("router" if ip == gw else "device")
            devices.append({"ip": ip, "mac": mac, "name": names.get(ip), "kind": kind})
        devices.sort(key=lambda d: ({"router": 0, "self": 1}.get(d["kind"], 2), tuple(int(x) for x in d["ip"].split("."))))
        return devices
