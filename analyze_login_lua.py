import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://t3y82cfb9raoyhor.myfritz.net:41284"

print("Analysiere /login.lua Response...")
print("="*70)

session = requests.Session()
session.verify = False

r = session.get(f"{BASE_URL}/login.lua", timeout=10)
print(f"Status: {r.status_code}")
print(f"Content-Type: {r.headers.get('content-type')}")
print("\nErste 1000 Zeichen der Response:")
print(r.text[:1000])

# Suche nach Challenge-Patterns
import re
patterns = [
    r'g_challenge\s*=\s*"([a-f0-9]+)"',
    r'var challenge\s*=\s*"([a-f0-9]+)"',
    r'\["security:status/challenge"\]\s*=\s*"([a-f0-9]+)"',
    r'challenge["\']\s*:\s*["\']([a-f0-9]+)["\']',
    r'Challenge["\']\s*:\s*["\']([a-f0-9]+)["\']',
]

print("\nSuche nach Challenge-Patterns:")
for pattern in patterns:
    match = re.search(pattern, r.text, re.IGNORECASE)
    if match:
        print(f"✓ Gefunden mit Pattern '{pattern}': {match.group(1)}")
    else:
        print(f"✗ Nicht gefunden: {pattern}")

# Speichere komplette Response
with open("login_lua_response.html", "w", encoding="utf-8") as f:
    f.write(r.text)
print("\nKomplette Response gespeichert in login_lua_response.html")
