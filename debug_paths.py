import os
import requests
from dotenv import load_dotenv
import urllib3

load_dotenv()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

FRITZ_URL = os.getenv("FRITZ_URL")

print(f"Testing different paths on: {FRITZ_URL}\n")

session = requests.Session()
session.verify = False
session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})

paths_to_test = [
    "/",
    "/index.html",
    "/home/home.lua",
    "/login.lua",
    "/login_sid.lua",
    "/cgi-bin/webcm",
    "/internet/inetstat_monitor.lua",
    "/net/network_user_devices.lua",
    "/data.lua",
]

for path in paths_to_test:
    url = f"{FRITZ_URL}{path}"
    try:
        response = session.get(url, timeout=5, allow_redirects=False)
        print(f"{path:40} -> HTTP {response.status_code}")
        if response.status_code == 200:
            print(f"   Content-Type: {response.headers.get('Content-Type')}")
            print(f"   Content length: {len(response.text)} bytes")
    except requests.exceptions.Timeout:
        print(f"{path:40} -> Timeout")
    except Exception as e:
        print(f"{path:40} -> Error: {str(e)[:60]}")

print("\n" + "="*70)
print("Trying MyFRITZ! detection...")
print("="*70)

# MyFRITZ-spezifische Endpunkte
myfritz_paths = [
    "/myfritz/areas.lua",
    "/myfritz/index.lua", 
    "/query.lua",
]

for path in myfritz_paths:
    url = f"{FRITZ_URL}{path}"
    try:
        response = session.get(url, timeout=5)
        print(f"{path:40} -> HTTP {response.status_code}")
    except Exception as e:
        print(f"{path:40} -> Error: {str(e)[:60]}")
