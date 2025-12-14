import os
import requests
from dotenv import load_dotenv
import urllib3
from bs4 import BeautifulSoup

load_dotenv()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

FRITZ_URL = os.getenv("FRITZ_URL")
FRITZ_USER = os.getenv("FRITZ_USER")
FRITZ_PASSWORD = os.getenv("FRITZ_PASSWORD")

print(f"Testing: {FRITZ_URL}")
print(f"User: {FRITZ_USER}\n")

session = requests.Session()
session.verify = False

# Browser-Headers
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'de,en-US;q=0.7,en;q=0.3',
})

# Test 1: Hauptseite
print("=== Test 1: Hauptseite ===")
try:
    response = session.get(FRITZ_URL, timeout=10, allow_redirects=True)
    print(f"Status: {response.status_code}")
    print(f"URL nach Redirect: {response.url}")
    print(f"Content-Type: {response.headers.get('Content-Type')}")
    print(f"Content (first 500 chars):\n{response.text[:500]}\n")
except Exception as e:
    print(f"Error: {e}\n")

# Test 2: /login_sid.lua direkt
print("=== Test 2: /login_sid.lua ===")
try:
    response = session.get(f"{FRITZ_URL}/login_sid.lua", timeout=10)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print(f"Content:\n{response.text[:500]}\n")
    else:
        print(f"Error content:\n{response.text[:500]}\n")
except Exception as e:
    print(f"Error: {e}\n")

# Test 3: Ohne HTTPS?
if FRITZ_URL.startswith("https://"):
    http_url = FRITZ_URL.replace("https://", "http://")
    print(f"=== Test 3: HTTP Version: {http_url} ===")
    try:
        response = session.get(http_url, timeout=10, allow_redirects=True)
        print(f"Status: {response.status_code}")
        print(f"URL nach Redirect: {response.url}")
        print(f"Content (first 300 chars):\n{response.text[:300]}\n")
    except Exception as e:
        print(f"Error: {e}\n")

# Test 4: Root ohne Port-Angabe
base_host = FRITZ_URL.split(":41284")[0] if ":41284" in FRITZ_URL else FRITZ_URL
if base_host != FRITZ_URL:
    print(f"=== Test 4: Basis-URL ohne Port: {base_host} ===")
    try:
        response = session.get(base_host, timeout=10, allow_redirects=True)
        print(f"Status: {response.status_code}")
        print(f"URL nach Redirect: {response.url}")
    except Exception as e:
        print(f"Error: {e}\n")
