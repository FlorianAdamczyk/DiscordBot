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

print("Login und Geräteabfrage über query.lua...")
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

# Holen der Liste
print("\n1) Abfrage: network=landevice:list")
resp = session.get(f"{BASE_URL}/query.lua", params={"sid": sid, "network": "landevice:list"}, timeout=15)
print(f"Status: {resp.status_code}")
print(f"Erste 500 Zeichen:\n{resp.text[:500]}")

# Versuche JSON zu parsen, sonst roh ausgeben
try:
    data = resp.json()
    print(f"\nGefundene Geräte: {len(data.get('landevice:list', []))}")
    target_uid = None
    for dev in data.get('landevice:list', []):
        mac = dev.get('macaddress', '').upper()
        uid = dev.get('uid') or dev.get('landevice') or dev.get('id')
        name = dev.get('name') or dev.get('hostname')
        print(f"- {name} | MAC {mac} | UID {uid}")
        if mac == TARGET_MAC:
            target_uid = uid
    print(f"\nTARGET UID: {target_uid}")
except Exception as e:
    print(f"JSON Parse Fehler: {e}")
    target_uid = None

print("\n2) Test: landevice:settings/wakeup mit UID vs MAC")
params_uid = {"sid": sid, "network": "landevice:settings/wakeup", "dev": target_uid or ""}
params_mac = {"sid": sid, "network": "landevice:settings/wakeup", "dev": TARGET_MAC.replace(':','')}

for label, params in [("UID", params_uid), ("MAC", params_mac)]:
    print(f"\nTest mit {label}:")
    r_get = session.get(f"{BASE_URL}/query.lua", params=params, timeout=10)
    print(f"  GET Status: {r_get.status_code}")
    print(f"  GET Antwort (200 chars): {r_get.text[:200]}")
    r_post = session.post(f"{BASE_URL}/query.lua", data=params, timeout=10)
    print(f"  POST Status: {r_post.status_code}")
    print(f"  POST Antwort (200 chars): {r_post.text[:200]}")

print("\n3) Zusätzliche data.lua WOL-Variante mit UID falls vorhanden")
if target_uid:
    params_data = {"sid": sid, "xhr": "1", "page": "netDev", "xhrId": "wakeup", "dev": target_uid}
    r_post = session.post(f"{BASE_URL}/data.lua", data=params_data, timeout=10)
    print(f"  data.lua POST Status: {r_post.status_code}")
    print(f"  data.lua Antwort (200 chars): {r_post.text[:200]}")
else:
    print("Keine UID gefunden; Überspringe data.lua UID-Test.")
