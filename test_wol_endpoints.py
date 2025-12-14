import requests
import hashlib
import xml.etree.ElementTree as ET
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

url = "https://t3y82cfb9raoyhor.myfritz.net:41284"
username = "renderbot"
password = "$@H2cTCAz!!Ej9I50l5IO424k$H@q#&Y"
mac = "44:8A:5B:D0:B6:4F"

print("Testing WOL Endpoints")
print("="*70)

# Login
print("\n1. Logging in...")
response = requests.get(f"{url}/login_sid.lua", verify=False, timeout=10)
root = ET.fromstring(response.text)
challenge = root.find('Challenge').text

challenge_password = f"{challenge}-{password}"
md5_hash = hashlib.md5(challenge_password.encode('utf-16le')).hexdigest()
response_str = f"{challenge}-{md5_hash}"

login_response = requests.get(
    f"{url}/login_sid.lua",
    params={'username': username, 'response': response_str},
    verify=False,
    timeout=10
)

root = ET.fromstring(login_response.text)
sid = root.find('SID').text

if sid == "0000000000000000":
    print("❌ Login failed!")
    exit(1)

print(f"✅ Logged in! SID: {sid}")

# Test verschiedene Endpunkte
mac_clean = mac.replace(":", "").upper()

endpoints_to_test = [
    # data.lua Varianten
    (f"{url}/data.lua", {"sid": sid, "page": "netDev", "xhrId": "wakeup", "wake": mac_clean}),
    (f"{url}/data.lua", {"sid": sid, "xhr": "1", "page": "netDev", "xhrId": "wakeup", "dev": mac_clean}),
    (f"{url}/data.lua", {"sid": sid, "page": "home", "xhrId": "wakeup", "wake": mac_clean}),
    
    # query.lua Varianten
    (f"{url}/query.lua", {"sid": sid, "network": "landevice:settings/wakeup", "dev": mac_clean}),
    
    # Webservices Varianten
    (f"{url}/webservices/homeautoswitch.lua", {"sid": sid, "switchcmd": "wakeup", "ain": mac_clean}),
    
    # Direkte WOL-Befehle
    (f"{url}/upnp/control/wakeup", {"sid": sid, "mac": mac}),
]

print(f"\n2. Testing WOL endpoints with MAC: {mac}")
print("="*70)

for endpoint_url, params in endpoints_to_test:
    print(f"\nTesting: {endpoint_url}")
    print(f"Params: {params}")
    
    try:
        # GET request
        response = requests.get(endpoint_url, params=params, verify=False, timeout=10)
        print(f"  GET Status: {response.status_code}")
        if response.status_code == 200:
            print(f"  Response (first 200 chars): {response.text[:200]}")
        
        # POST request
        response = requests.post(endpoint_url, data=params, verify=False, timeout=10)
        print(f"  POST Status: {response.status_code}")
        if response.status_code == 200:
            print(f"  Response (first 200 chars): {response.text[:200]}")
            
    except Exception as e:
        print(f"  Error: {e}")

# Test auch ohne MAC, nur um Seiten-Zugriff zu prüfen
print("\n\n3. Testing page access (without WOL action)")
print("="*70)

pages = [
    f"{url}/net/network_user_devices.lua?sid={sid}",
    f"{url}/internet/inetstat_monitor.lua?sid={sid}",
    f"{url}/data.lua?sid={sid}&page=netDev",
    f"{url}/homeauto/homeauto.lua?sid={sid}",
]

for page_url in pages:
    try:
        response = requests.get(page_url, verify=False, timeout=10)
        print(f"\n{page_url}")
        print(f"  Status: {response.status_code}")
        if response.status_code == 200:
            print(f"  Content length: {len(response.text)}")
    except Exception as e:
        print(f"  Error: {e}")
