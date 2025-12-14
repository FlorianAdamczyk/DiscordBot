import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

url = "https://giessencraft.ddns.net:41284/"

# Test mit verschiedenen Header-Kombinationen
configs = [
    {
        "name": "Minimal (nur URL)",
        "headers": {}
    },
    {
        "name": "Standard Browser",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }
    },
    {
        "name": "Mit Host Header",
        "headers": {
            "Host": "giessencraft.ddns.net:41284",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
    }
]

for config in configs:
    print(f"\n{'='*70}")
    print(f"Test: {config['name']}")
    print(f"{'='*70}")
    
    try:
        response = requests.get(
            url,
            headers=config['headers'],
            verify=False,
            timeout=10
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Reason: {response.reason}")
        print(f"\nResponse Headers:")
        for key, value in response.headers.items():
            print(f"  {key}: {value}")
        
        print(f"\nResponse Content (first 500 chars):")
        print(response.text[:500])
        
        # Prüfe auf Redirect-Informationen
        if response.history:
            print(f"\nRedirect History:")
            for resp in response.history:
                print(f"  {resp.status_code} -> {resp.url}")
        
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")

# Versuche auch HTTP (ohne S)
print(f"\n{'='*70}")
print(f"Test: HTTP (ohne TLS)")
print(f"{'='*70}")
try:
    response = requests.get(
        "http://giessencraft.ddns.net:41284/",
        timeout=5
    )
    print(f"Status Code: {response.status_code}")
    print(response.text[:500])
except Exception as e:
    print(f"Error: {e}")
