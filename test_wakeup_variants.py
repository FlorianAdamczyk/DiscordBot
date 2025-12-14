import requests, hashlib, xml.etree.ElementTree as ET, urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
BASE_URL = "https://t3y82cfb9raoyhor.myfritz.net:41284"
USERNAME = "renderbot"
PASSWORD = "$@H2cTCAz!!Ej9I50l5IO424k$H@q#&Y"
MAC = "44:8A:5B:D0:B6:4F"

s = requests.Session(); s.verify=False
# login
r = s.get(f"{BASE_URL}/login_sid.lua"); ch = ET.fromstring(r.text).find('Challenge').text
resp = f"{ch}-{hashlib.md5(f'{ch}-{PASSWORD}'.encode('utf-16le')).hexdigest()}"
r = s.get(f"{BASE_URL}/login_sid.lua", params={"username":USERNAME,"response":resp}); sid = ET.fromstring(r.text).find('SID').text
print("SID:", sid)

mac_clean = MAC.replace(':','').upper()
for dev in [mac_clean, f"landevice:{mac_clean}"]:
    params = {"sid":sid, "xhr":"1", "page":"netDev", "xhrId":"wakeup", "dev": dev}
    print("\nPOST", params)
    r = s.post(f"{BASE_URL}/data.lua", data=params, timeout=10)
    print("Status:", r.status_code)
    print("Body:", r.text[:200])
