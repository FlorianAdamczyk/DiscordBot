import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

url = "https://giessencraft.ddns.net:41284/"

try:
    response = requests.get(url, verify=False, timeout=10)
    
    print(f"Status Code: {response.status_code}")
    print(f"\nFull Response Content:")
    print("="*70)
    print(response.text)
    print("="*70)
    
    # Speichere auch in Datei
    with open("fritzbox_response.html", "w", encoding="utf-8") as f:
        f.write(response.text)
    print("\nResponse saved to fritzbox_response.html")
    
except Exception as e:
    print(f"Error: {e}")
