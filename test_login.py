import requests
import hashlib
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

url = "https://t3y82cfb9raoyhor.myfritz.net:41284"
username = "renderbot"
password = "$@H2cTCAz!!Ej9I50l5IO424k$H@q#&Y"

print("Testing FRITZ!Box Login")
print("="*70)

# Schritt 1: Challenge holen
print("\n1. Getting Challenge...")
response = requests.get(f"{url}/login_sid.lua", verify=False, timeout=10)
print(f"Status: {response.status_code}")
print(f"Response:\n{response.text}")

# Parse XML
import xml.etree.ElementTree as ET
root = ET.fromstring(response.text)
challenge = root.find('Challenge').text
sid = root.find('SID').text
block_time = root.find('BlockTime').text

print(f"\nChallenge: {challenge}")
print(f"Initial SID: {sid}")
print(f"Block Time: {block_time}")

if int(block_time) > 0:
    print(f"\n❌ Account is blocked for {block_time} seconds!")
    exit(1)

# Schritt 2: Response berechnen
# Format: challenge + "-" + MD5(challenge + "-" + password)
# Aber: Password muss als UTF-16LE kodiert werden!
print("\n2. Calculating response...")

challenge_password = f"{challenge}-{password}"
# Encode as UTF-16LE
challenge_password_bytes = challenge_password.encode('utf-16le')
# Calculate MD5
md5_hash = hashlib.md5(challenge_password_bytes).hexdigest()
response_str = f"{challenge}-{md5_hash}"

print(f"Challenge-Password String: {challenge_password[:30]}...")
print(f"MD5 Hash: {md5_hash}")
print(f"Response String: {response_str}")

# Schritt 3: Login durchführen
print("\n3. Performing login...")
login_response = requests.get(
    f"{url}/login_sid.lua",
    params={
        'username': username,
        'response': response_str
    },
    verify=False,
    timeout=10
)

print(f"Status: {login_response.status_code}")
print(f"Response:\n{login_response.text}")

# Parse result
root = ET.fromstring(login_response.text)
new_sid = root.find('SID').text
rights = root.find('Rights')

print(f"\nNew SID: {new_sid}")
if rights is not None and rights.text:
    print(f"Rights: {rights.text}")

if new_sid != "0000000000000000":
    print("\n✅ LOGIN SUCCESSFUL!")
else:
    print("\n❌ LOGIN FAILED - SID is still 0")
    block_time = root.find('BlockTime').text
    if int(block_time) > 0:
        print(f"Account is now blocked for {block_time} seconds!")
