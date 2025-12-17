import requests
import hashlib
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://t3y82cfb9raoyhor.myfritz.net:41284"
USERNAME = "renderbot"
PASSWORD = "$@H2cTCAz!!Ej9I50l5IO424k$H@q#&Y"
MAC = "44:8A:5B:D0:B6:4F"

print("Teste fritzwol-Ansatz: /cgi-bin/webcm mit wakeup:settings/mac")
print("="*70)

session = requests.Session()
session.verify = False

# Login (wie im Perl-Script)
print("\n1. Login über /login.lua...")
r = session.get(f"{BASE_URL}/login.lua", timeout=10)
content = r.text

# Challenge extrahieren (aus JSON im Script-Tag)
import json
import re
challenge_match = re.search(r'const data = ({.*?});', content, re.DOTALL)
if not challenge_match:
    print("❌ JSON-Daten nicht gefunden!")
    exit(1)

try:
    data_json = json.loads(challenge_match.group(1))
    challenge = data_json.get('challenge')
    if not challenge:
        print("❌ Challenge nicht im JSON gefunden!")
        exit(1)
except json.JSONDecodeError as e:
    print(f"❌ JSON-Parse-Fehler: {e}")
    exit(1)

print(f"Challenge: {challenge}")

# Response berechnen (MD5 mit UTF-16LE wie im Perl-Script)
import hashlib

# Extrahiere nur den ersten Teil der Challenge für MD5
challenge_part = challenge.split('$')[0] if '$' in challenge else challenge

pass_utf16le = f"{challenge_part}-{PASSWORD}".encode('utf-16le')
md5_hash = hashlib.md5(pass_utf16le).hexdigest()
response_str = f"{challenge_part}-{md5_hash}"

print(f"Response: {response_str} (MD5 mit Challenge-Teil: {challenge_part})")

# Login durchführen
login_data = {
    "username": USERNAME,
    "response": response_str
}
r = session.post(f"{BASE_URL}/login.lua", data=login_data, timeout=10)
content = r.text

print(f"Login-Response Status: {r.status_code}")
print(f"Login-Response Content: {content[:1000]}")

if "error_text" in content.lower() or "ErrorMsg" in content.lower():
    print("❌ Login fehlgeschlagen!")
    exit(1)

# SID extrahieren
sid_match = re.search(r'(?:home|logout)\.lua\?sid=([a-f0-9]+)', content)
if not sid_match:
    print("❌ SID nicht gefunden!")
    exit(1)

sid = sid_match.group(1)
print(f"SID: {sid}")

# Wake-up über /cgi-bin/webcm (wie im Perl-Script)
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
