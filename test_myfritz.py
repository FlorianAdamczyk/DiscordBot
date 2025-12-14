import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

url = "https://t3y82cfb9raoyhor.myfritz.net:41284/"

print(f"Testing: {url}")
print("="*70)

try:
    response = requests.get(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        },
        verify=False,
        timeout=10
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Content Length: {len(response.text)}")
    print(f"\nFirst 1000 chars of response:")
    print(response.text[:1000])
    
    if response.status_code == 200:
        print("\n✅ SUCCESS! Die URL funktioniert!")
        
        # Speichere die Response
        with open("myfritz_response.html", "w", encoding="utf-8") as f:
            f.write(response.text)
        print("Response saved to myfritz_response.html")
        
except Exception as e:
    print(f"❌ Error: {e}")

# Teste auch /login_sid.lua
print("\n" + "="*70)
print("Testing /login_sid.lua endpoint...")
print("="*70)

try:
    response = requests.get(
        "https://t3y82cfb9raoyhor.myfritz.net:41284/login_sid.lua",
        verify=False,
        timeout=10
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"\nResponse:")
    print(response.text[:500])
    
except Exception as e:
    print(f"Error: {e}")
