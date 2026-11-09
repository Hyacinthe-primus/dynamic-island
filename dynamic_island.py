"""Point d'entrée de l'application installée (DynamicIsland.exe).

- Sans argument : démarre le gardien, qui lance l'île et la relance si elle plante.
- --island : l'île elle-même (lancée par le gardien).
- --selftest : vérifie que chaque composant fonctionne et écrit un rapport dans %TEMP%\\DynamicIsland-selftest.txt.
Depuis les sources, `pythonw island.py` (ou start.bat) reste utilisable."""
import sys


def selftest():
    import os
    import tempfile
    import traceback
    results = []

    def check(name, fn):
        try:
            info = fn()
            results.append(f"OK    {name}" + (f" — {info}" if info else ""))
        except Exception as e:
            results.append(f"ÉCHEC {name} — {type(e).__name__}: {e}")
            results.append("      " + traceback.format_exc().strip().splitlines()[-1])

    def media():
        import asyncio
        from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as M
        async def get():
            return await M.request_async()
        m = asyncio.run(get())
        s = m.get_current_session()
        return f"session : {s.source_app_user_model_id if s else 'aucune'}"

    def audio():
        from pycaw.pycaw import AudioUtilities
        sp = AudioUtilities.GetSpeakers()
        return f"{sp.FriendlyName} · volume {sp.EndpointVolume.GetMasterVolumeLevelScalar():.2f}"

    def uia():
        import comtypes.client
        comtypes.client.GetModule("UIAutomationCore.dll")
        from comtypes.gen import UIAutomationClient  # noqa: F401
        return "module UI Automation généré"

    def radios():
        import asyncio
        from winrt.windows.devices.radios import Radio
        async def get():
            return await Radio.get_radios_async()
        return ", ".join(f"{r.name}={int(r.state)}" for r in asyncio.run(get()))

    def bluetooth():
        import asyncio
        from winrt.windows.devices.bluetooth import BluetoothDevice
        from winrt.windows.devices.enumeration import DeviceInformation

        async def n():
            return len(await DeviceInformation.find_all_async_aqs_filter(
                BluetoothDevice.get_device_selector_from_pairing_state(True)))
        return f"{asyncio.run(n())} appareil(s) appairé(s)"

    def notifications():
        from winrt.windows.ui.notifications.management import UserNotificationListener
        return f"accès {int(UserNotificationListener.current.get_access_status())}"

    def hotspot():
        from winrt.windows.networking.connectivity import NetworkInformation
        from winrt.windows.networking.networkoperators import NetworkOperatorTetheringManager as Mg
        m = Mg.create_from_connection_profile(NetworkInformation.get_internet_connection_profile())
        return f"état {int(m.tethering_operational_state)}, SSID {m.get_current_access_point_configuration().ssid}"

    def crypto():
        import phone
        d = tempfile.mkdtemp()
        old = phone.APPDATA
        phone.APPDATA = d
        try:
            phone.settings.pop("phone_cert_ip", None)
            c, k = phone.ensure_cert("127.0.0.1")
            return f"certificat {os.path.getsize(c)} octets"
        finally:
            phone.APPDATA = old

    def misc():
        import qrcode
        import zoneinfo

        import icalendar  # noqa: F401
        import recurring_ical_events  # noqa: F401
        qrcode.QRCode().add_data("test")
        zoneinfo.ZoneInfo("Africa/Lome")
        return "qrcode, icalendar, fuseaux horaires"

    def qt():
        from PySide6.QtGui import QImageReader
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication(sys.argv)
        fmts = {bytes(f).decode() for f in QImageReader.supportedImageFormats()}
        return "formats d'image : " + ", ".join(sorted(f for f in fmts if f in ("png", "jpg", "ico", "webp", "svg")))

    def files_():
        from paths import resource
        for f in ("phone_page.html", os.path.join("assets", "island.ico")):
            if not os.path.exists(resource(f)):
                raise FileNotFoundError(f)
        return "phone_page.html, island.ico"

    def brightness():
        import screen_brightness_control as sbc
        return f"{sbc.get_brightness(display=0)}"

    for name, fn in (("Fichiers de l'application", files_), ("Qt / images", qt), ("Média (Windows)", media),
                     ("Audio", audio), ("UI Automation (Ne pas déranger)", uia), ("Radios Wi-Fi / Bluetooth", radios),
                     ("Bluetooth", bluetooth), ("Notifications", notifications), ("Point d'accès", hotspot),
                     ("Luminosité", brightness), ("Certificat HTTPS téléphone", crypto), ("Divers", misc)):
        check(name, fn)
    out = os.path.join(tempfile.gettempdir(), "DynamicIsland-selftest.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(results) + "\n")


def main():
    if "--selftest" in sys.argv:
        selftest()
    elif "--island" in sys.argv:
        import island
        island.main()
    else:
        import watchdog
        watchdog.main()


if __name__ == "__main__":
    main()
