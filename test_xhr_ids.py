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

# Test different xhrId values
xhr_ids = ['wakeup', 'all', 'edit', 'status', 'power', 'energy']

for xhr_id in xhr_ids:
    print(f'Testing xhrId: {xhr_id}')
    try:
        r = session.post(f"{BASE_URL}/data.lua", data={"sid": sid, "xhr": "1", "page": "netDev", "xhrId": xhr_id, "uid": "landevice4123"}, timeout=10)
        print(f'  Status: {r.status_code}')
        if r.status_code == 200:
            try:
                js = r.json()
                print(f'  Keys: {list(js.keys()) if isinstance(js, dict) else "not json"}')
            except:
                print(f'  Content: {r.text[:200]}')
    except Exception as e:
        print(f'  Error: {e}')
    print()