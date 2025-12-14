import requests
import hashlib
import xml.etree.ElementTree as ET
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://t3y82cfb9raoyhor.myfritz.net:41284"
USERNAME = "renderbot"
PASSWORD = "$@H2cTCAz!!Ej9I50l5IO424k$H@q#&Y"
TARGET_MAC = "44:8A:5B:D0:B6:4F".upper()

session = requests.Session()
session.verify = False
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json, text/plain, */*"
})

print("Login und netDev-Liste über data.lua...")
print("="*70)

# Login
resp = session.get(f"{BASE_URL}/login_sid.lua", timeout=10)
root = ET.fromstring(resp.text)
challenge = root.find('Challenge').text
cp = f"{challenge}-{PASSWORD}".encode('utf-16le')
md5 = hashlib.md5(cp).hexdigest()
response_str = f"{challenge}-{md5}"
resp = session.get(f"{BASE_URL}/login_sid.lua", params={"username": USERNAME, "response": response_str}, timeout=10)
root = ET.fromstring(resp.text)
sid = root.find('SID').text
print(f"SID: {sid}")
if sid == "0000000000000000":
    print("❌ Login fehlgeschlagen")
    raise SystemExit(1)

# netDev Seite abrufen (XHR)
params = {"sid": sid, "xhr": "1", "page": "netDev"}
resp = session.get(f"{BASE_URL}/data.lua", params=params, timeout=15)
print(f"Status: {resp.status_code}")
text = resp.text
print(f"Erste 400 Zeichen:\n{text[:400]}")

# Versuche JSON zu parsen
try:
    data = resp.json()
    print("\nKeys:", list(data.keys()))
    devices = data.get('data', {}).get('net', {}).get('devices') or data.get('devices') or data.get('net', {}).get('devices')
    if devices is None:
        print("Geräteliste nicht direkt gefunden; Drucke Struktur grob:")
        import json
        print(json.dumps(data, indent=2)[:2000])
    else:
        print(f"Gefundene Geräte: {len(devices)}")
        target_dev = None
        for dev in devices:
            mac = (dev.get('mac') or dev.get('macaddress') or '').upper()
            uid = dev.get('uid') or dev.get('id') or dev.get('landevice') or dev.get('dev')
            name = dev.get('name') or dev.get('hostname') or dev.get('friendlyname')
            print(f"- {name} | MAC {mac} | UID {uid}")
            if mac.replace(':','') == TARGET_MAC.replace(':',''):
                target_dev = (uid or mac.replace(':',''))
        print("TARGET DEV:", target_dev)
        
        if target_dev:
            # Versuche WOL mit dev
            wol_params = {"sid": sid, "xhr": "1", "page": "netDev", "xhrId": "wakeup", "dev": target_dev}
            r_post = session.post(f"{BASE_URL}/data.lua", data=wol_params, timeout=10)
            print(f"WOL POST Status: {r_post.status_code}")
            print(f"WOL Antwort (200 chars): {r_post.text[:200]}")
        else:
            print("Zielgerät nicht gefunden in netDev-Liste.")
except Exception as e:
    print("JSON Parse Fehler:", e)
    print("Rohtext (600 chars):\n", text[:600])
