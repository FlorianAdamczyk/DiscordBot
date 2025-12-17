import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://t3y82cfb9raoyhor.myfritz.net:41284"
USERNAME = "renderbot"
PASSWORD = "$@H2cTCAz!!Ej9I50l5IO424k$H@q#&Y"
MAC = "44:8A:5B:D0:B6:4F"

session = requests.Session()
session.verify = False

# Login
import hashlib
import xml.etree.ElementTree as ET
response = session.get(f"{BASE_URL}/login_sid.lua", timeout=15)
root = ET.fromstring(response.text)
challenge = root.find('Challenge').text
challenge_password = f"{challenge}-{PASSWORD}"
md5_hash = hashlib.md5(challenge_password.encode('utf-16le')).hexdigest()
response_str = f"{challenge}-{md5_hash}"
response = session.get(f"{BASE_URL}/login_sid.lua", params={"username": USERNAME, "response": response_str}, timeout=15)
root = ET.fromstring(response.text)
sid = root.find('SID').text

print(f"SID: {sid}")

# Device status
r = session.post(f"{BASE_URL}/data.lua", data={"sid": sid, "xhr": "1", "page": "netDev", "xhrId": "devices"})
js = r.json()
for dev in js.get('data', {}).get('active', []) + js.get('data', {}).get('passive', []):
    if dev.get('mac', '').upper() == MAC.upper():
        state = dev.get('state', {})
        state_class = state.get('class') if isinstance(state, dict) else None
        is_online = state_class == 'globe_online'
        print(f'Gerät: {dev.get("name")} - {"ONLINE" if is_online else "OFFLINE"} (state.class={state_class})')
        break