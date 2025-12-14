import requests
import hashlib
import xml.etree.ElementTree as ET
import urllib3
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://t3y82cfb9raoyhor.myfritz.net:41284"
USERNAME = "renderbot"
PASSWORD = "$@H2cTCAz!!Ej9I50l5IO424k$H@q#&Y"
MAC = "44:8A:5B:D0:B6:4F"

def login_and_get_sid(session):
    """Login und SID holen"""
    r = session.get(f"{BASE_URL}/login_sid.lua")
    root = ET.fromstring(r.text)
    challenge = root.find('Challenge').text
    
    cp = f"{challenge}-{PASSWORD}".encode('utf-16le')
    md5 = hashlib.md5(cp).hexdigest()
    resp = f"{challenge}-{md5}"
    
    r = session.get(f"{BASE_URL}/login_sid.lua", params={"username": USERNAME, "response": resp})
    root = ET.fromstring(r.text)
    sid = root.find('SID').text
    return sid

def get_device_uid(session, sid):
    """UID des Servers holen"""
    r = session.post(f"{BASE_URL}/data.lua", data={"sid": sid, "xhr": "1", "page": "netDev", "xhrId": "devices"})
    js = r.json()
    for dev in js.get('data', {}).get('active', []) + js.get('data', {}).get('passive', []):
        if dev.get('mac', '').upper() == MAC.upper():
            return dev.get('UID')
    return None

print("="*70)
print("FRITZBOX WOL DEBUG - Systematische Tests")
print("="*70)

session = requests.Session()
session.verify = False

# Login
print("\n1. Login...")
sid = login_and_get_sid(session)
print(f"SID: {sid}")

# UID holen
print("\n2. Device UID ermitteln...")
uid = get_device_uid(session, sid)
print(f"UID: {uid}")

if not uid:
    print("FEHLER: UID nicht gefunden!")
    exit(1)

# Verschiedene Varianten testen
print("\n3. Teste verschiedene WOL-Request-Varianten...")
print("="*70)

variants = [
    {
        "name": "POST mit data (aktuelle Methode)",
        "method": "POST",
        "url": f"{BASE_URL}/data.lua",
        "params": None,
        "data": {"sid": sid, "xhr": "1", "lang": "de", "page": "netDev", "xhrId": "wakeup", "dev": uid},
        "headers": {"Content-Type": "application/x-www-form-urlencoded"}
    },
    {
        "name": "GET mit params",
        "method": "GET",
        "url": f"{BASE_URL}/data.lua",
        "params": {"sid": sid, "xhr": "1", "lang": "de", "page": "netDev", "xhrId": "wakeup", "dev": uid},
        "data": None,
        "headers": {}
    },
    {
        "name": "POST ohne xhr",
        "method": "POST",
        "url": f"{BASE_URL}/data.lua",
        "params": None,
        "data": {"sid": sid, "lang": "de", "page": "netDev", "xhrId": "wakeup", "dev": uid},
        "headers": {"Content-Type": "application/x-www-form-urlencoded"}
    },
    {
        "name": "POST mit wake statt dev",
        "method": "POST",
        "url": f"{BASE_URL}/data.lua",
        "params": None,
        "data": {"sid": sid, "xhr": "1", "lang": "de", "page": "netDev", "xhrId": "wakeup", "wake": uid},
        "headers": {"Content-Type": "application/x-www-form-urlencoded"}
    },
    {
        "name": "POST mit page=home",
        "method": "POST",
        "url": f"{BASE_URL}/data.lua",
        "params": None,
        "data": {"sid": sid, "xhr": "1", "lang": "de", "page": "home", "xhrId": "wakeup", "dev": uid},
        "headers": {"Content-Type": "application/x-www-form-urlencoded"}
    },
    {
        "name": "POST mit apply",
        "method": "POST",
        "url": f"{BASE_URL}/data.lua",
        "params": None,
        "data": {"sid": sid, "xhr": "1", "lang": "de", "page": "netDev", "xhrId": "wakeup", "dev": uid, "apply": ""},
        "headers": {"Content-Type": "application/x-www-form-urlencoded"}
    },
    {
        "name": "POST ohne lang",
        "method": "POST",
        "url": f"{BASE_URL}/data.lua",
        "params": None,
        "data": {"sid": sid, "xhr": "1", "page": "netDev", "xhrId": "wakeup", "dev": uid},
        "headers": {"Content-Type": "application/x-www-form-urlencoded"}
    },
    {
        "name": "GET an /command.lua",
        "method": "GET",
        "url": f"{BASE_URL}/command.lua",
        "params": {"sid": sid, "wakeup": uid},
        "data": None,
        "headers": {}
    },
    {
        "name": "POST mit oldpage",
        "method": "POST",
        "url": f"{BASE_URL}/data.lua",
        "params": None,
        "data": {"sid": sid, "xhr": "1", "lang": "de", "page": "netDev", "xhrId": "wakeup", "dev": uid, "oldpage": "/net/network_user_devices.lua"},
        "headers": {"Content-Type": "application/x-www-form-urlencoded"}
    },
]

for i, variant in enumerate(variants, 1):
    print(f"\n[{i}/{len(variants)}] {variant['name']}")
    print("-"*70)
    
    try:
        session.headers.update(variant["headers"])
        
        if variant["method"] == "GET":
            r = session.get(variant["url"], params=variant["params"], timeout=10)
        else:
            r = session.post(variant["url"], params=variant["params"], data=variant["data"], timeout=10)
        
        print(f"Status: {r.status_code}")
        
        # Versuche JSON zu parsen
        try:
            js = r.json()
            print(f"JSON Keys: {list(js.keys())}")
            if "data" in js:
                print(f"  data keys: {list(js.get('data', {}).keys())}")
            print(f"Body (200 chars): {str(js)[:200]}")
        except:
            print(f"Body (200 chars): {r.text[:200]}")
        
        # Prüfe ob Gerät jetzt online ist
        print("\n  Prüfe Device-Status nach Request...")
        check_r = session.post(f"{BASE_URL}/data.lua", data={"sid": sid, "xhr": "1", "page": "netDev", "xhrId": "devices"})
        check_js = check_r.json()
        for dev in check_js.get('data', {}).get('active', []) + check_js.get('data', {}).get('passive', []):
            if dev.get('UID') == uid:
                state = dev.get('state', {})
                state_class = state.get('class') if isinstance(state, dict) else None
                is_online = state_class == 'globe_online'
                print(f"  → Gerät '{dev.get('name')}': {'ONLINE' if is_online else 'OFFLINE'} (state.class={state_class})")
                break
        
    except Exception as e:
        print(f"FEHLER: {e}")

print("\n" + "="*70)
print("Tests abgeschlossen")
print("Wenn eines der Tests den Server online zeigt, ist das die richtige Variante!")
print("="*70)
