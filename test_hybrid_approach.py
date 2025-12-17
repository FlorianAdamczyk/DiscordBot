import requests
import xml.etree.ElementTree as ET
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://t3y82cfb9raoyhor.myfritz.net:41284"
USERNAME = "renderbot"
PASSWORD = "$@H2cTCAz!!Ej9I50l5IO424k$H@q#&Y"
MAC = "44:8A:5B:D0:B6:4F"

print("Teste hybriden Ansatz: Login wie main.py, WOL wie fritzwol")
print("="*70)

session = requests.Session()
session.verify = False

# Login wie in main.py (funktioniert)
print("\n1. Login über /login_sid.lua...")
import hashlib
import xml.etree.ElementTree as ET

login_url = f"{BASE_URL}/login_sid.lua"
response = session.get(login_url, timeout=15)

if response.status_code != 200:
    print(f"❌ Login-Seite nicht erreichbar (HTTP {response.status_code})")
    exit(1)

# Parse XML response
try:
    root = ET.fromstring(response.text)
    challenge = root.find('Challenge').text
    sid = root.find('SID').text
    block_time = root.find('BlockTime').text

    if int(block_time) > 0:
        print(f"❌ Account ist für {block_time} Sekunden gesperrt")
        exit(1)

    # Check if already logged in
    if sid != "0000000000000000":
        print("Session bereits aktiv, nutze bestehende SID")
    else:
        # Response berechnen (MD5-Challenge-Response-Verfahren)
        challenge_password = f"{challenge}-{PASSWORD}"
        md5_hash = hashlib.md5(challenge_password.encode('utf-16le')).hexdigest()
        response_str = f"{challenge}-{md5_hash}"

        # Login durchführen
        login_params = {
            "username": USERNAME,
            "response": response_str
        }
        response = session.get(login_url, params=login_params, timeout=15)

        if response.status_code != 200:
            print(f"❌ Login fehlgeschlagen (HTTP {response.status_code})")
            exit(1)

        # Parse SID
        root = ET.fromstring(response.text)
        sid = root.find('SID').text

        if sid == "0000000000000000":
            print("❌ Login fehlgeschlagen - Benutzername oder Passwort falsch")
            exit(1)

        print(f"SID: {sid}")

except Exception as e:
    print(f"❌ XML-Parsing fehlgeschlagen: {str(e)}")
    exit(1)

# Wake-up über /cgi-bin/webcm (wie fritzwol)
print("\n2. Wake-up über /cgi-bin/webcm...")
wakeup_data = {
    "sid": sid,
    "wakeup:settings/mac": MAC
}
r = session.post(f"{BASE_URL}/cgi-bin/webcm", data=wakeup_data, timeout=10)

print(f"Status: {r.status_code}")
print(f"Response: {r.text[:500]}")

if r.status_code == 200 and "error" not in r.text.lower():
    print("✅ Wake-up erfolgreich!")
else:
    print("❌ Wake-up fehlgeschlagen!")

# Prüfe Device-Status
print("\n3. Prüfe Device-Status...")
r = session.post(f"{BASE_URL}/data.lua", data={"sid": sid, "xhr": "1", "page": "netDev", "xhrId": "devices"})
js = r.json()
for dev in js.get('data', {}).get('active', []) + js.get('data', {}).get('passive', []):
    if dev.get('mac', '').upper() == MAC.upper():
        state = dev.get('state', {})
        state_class = state.get('class') if isinstance(state, dict) else None
        is_online = state_class == 'globe_online'
        print(f"→ Gerät '{dev.get('name')}': {'ONLINE' if is_online else 'OFFLINE'} (state.class={state_class})")
        break