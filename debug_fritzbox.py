import os
import requests
from dotenv import load_dotenv
import urllib3

load_dotenv()

# SSL-Warnungen unterdrücken
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

FRITZ_IP = os.getenv("FRITZ_IP")
FRITZ_PORT = os.getenv("FRITZ_PORT", "49443")
FRITZ_USER = os.getenv("FRITZ_USER", "").strip('"')
FRITZ_PASSWORD = os.getenv("FRITZ_PASSWORD", "").strip('"')

print(f"Testing connection to: https://{FRITZ_IP}:{FRITZ_PORT}")
print(f"User: {repr(FRITZ_USER)}")
print(f"Password length: {len(FRITZ_PASSWORD)} chars")
print()

# Versuche die XML-Beschreibung abzurufen
url = f"https://{FRITZ_IP}:{FRITZ_PORT}/tr064desc.xml"
print(f"Requesting: {url}")

try:
    response = requests.get(
        url,
        auth=(FRITZ_USER, FRITZ_PASSWORD),
        verify=False,  # SSL-Verifikation deaktiviert
        timeout=10
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Content-Type: {response.headers.get('Content-Type')}")
    print()
    print("=== Response Content (first 1000 chars) ===")
    print(response.text[:1000])
    print()
    
    if response.status_code == 401:
        print("❌ Authentication failed! Check username and password.")
    elif response.status_code == 200:
        if "<?xml" in response.text:
            print("✅ Valid XML response - Authentication seems OK")
        else:
            print("❌ Response is not XML - might be an error page")
    else:
        print(f"❌ Unexpected status code: {response.status_code}")
        
except requests.exceptions.RequestException as e:
    print(f"❌ Connection error: {e}")

# Alternative URLs to try
alternative_urls = [
    f"https://{FRITZ_IP}:{FRITZ_PORT}/igddesc.xml",
    f"https://{FRITZ_IP}:{FRITZ_PORT}/igdicfgSCPD.xml",
]

print("\n=== Testing alternative URLs ===")
for alt_url in alternative_urls:
    try:
        response = requests.get(alt_url, auth=(FRITZ_USER, FRITZ_PASSWORD), verify=False, timeout=5)
        print(f"{alt_url}: Status {response.status_code}")
    except Exception as e:
        print(f"{alt_url}: Error - {e}")
