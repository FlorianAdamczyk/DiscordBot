import requests
import hashlib
import xml.etree.ElementTree as ET
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://t3y82cfb9raoyhor.myfritz.net:41284"
USERNAME = "renderbot"
PASSWORD = "$@H2cTCAz!!Ej9I50l5IO424k$H@q#&Y"

session = requests.Session()
session.verify = False
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json, text/plain, */*"
})

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

variants = [
    {"xhrId": "devices"},
    {"xhrId": "device"},
    {"xhrId": "list"},
    {"xhrId": "wakeup"},
    {"xhrId": "netDev"},
]

for var in variants:
    params = {"sid": sid, "xhr": "1", "page": "netDev", **var}
    print("\nTesting:", params)
    try:
        r = session.get(f"{BASE_URL}/data.lua", params=params, timeout=10)
        print("GET", r.status_code, r.text[:300])
        r = session.post(f"{BASE_URL}/data.lua", data=params, timeout=10)
        print("POST", r.status_code)
        open(f"netdev_{var['xhrId']}_post.json","w",encoding="utf-8").write(r.text)
        print("Gespeichert:", f"netdev_{var['xhrId']}_post.json")
    except Exception as e:
        print("Error:", e)
