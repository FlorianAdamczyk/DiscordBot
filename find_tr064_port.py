import os
import requests
from dotenv import load_dotenv
import urllib3

load_dotenv()

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

FRITZ_IP = os.getenv("FRITZ_IP")
FRITZ_USER = os.getenv("FRITZ_USER", "").strip('"')
FRITZ_PASSWORD = os.getenv("FRITZ_PASSWORD", "").strip('"')

# Alle möglichen TR-064 Ports testen
ports_to_test = [
    (49443, "https", "Standard TR-064 HTTPS"),
    (49000, "http", "Standard TR-064 HTTP"),
    (41284, "https", "Konfigurierter Port"),
]

print(f"Testing FritzBox: {FRITZ_IP}")
print(f"User: {repr(FRITZ_USER)}\n")

for port, protocol, description in ports_to_test:
    url = f"{protocol}://{FRITZ_IP}:{port}/tr064desc.xml"
    print(f"=== {description} ({protocol}://{FRITZ_IP}:{port}) ===")
    
    try:
        response = requests.get(
            url,
            auth=(FRITZ_USER, FRITZ_PASSWORD),
            verify=False,
            timeout=5
        )
        
        print(f"✓ Connection successful!")
        print(f"  Status: {response.status_code}")
        print(f"  Content-Type: {response.headers.get('Content-Type', 'unknown')}")
        
        if response.status_code == 200 and "<?xml" in response.text:
            print(f"  ✅ VALID XML - This port works!")
            print(f"\n  Update your .env file:")
            print(f"  FRITZ_PORT={port}")
            break
        elif response.status_code == 401:
            print(f"  ❌ Authentication failed (401)")
        elif response.status_code == 400:
            print(f"  ❌ Bad Request (400) - Wrong endpoint")
        else:
            print(f"  ⚠️ Unexpected response")
            
    except requests.exceptions.Timeout:
        print(f"  ❌ Timeout - Port not reachable")
    except requests.exceptions.ConnectionError as e:
        print(f"  ❌ Connection failed: {str(e)[:100]}")
    except Exception as e:
        print(f"  ❌ Error: {str(e)[:100]}")
    
    print()
