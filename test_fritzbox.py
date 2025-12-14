import os
from dotenv import load_dotenv
from fritzconnection import FritzConnection

load_dotenv()

# Environment Variables
FRITZ_IP = os.getenv("FRITZ_IP")
FRITZ_USER = os.getenv("FRITZ_USER")
FRITZ_PASSWORD = os.getenv("FRITZ_PASSWORD")
SERVER_MAC = os.getenv("SERVER_MAC")
FRITZ_PORT = os.getenv("FRITZ_PORT", "49443")  # Standard TR-064 HTTPS Port

print(f"Testing FritzBox connection to: {FRITZ_IP}:{FRITZ_PORT}")
print(f"User: {FRITZ_USER}")
print(f"MAC: {SERVER_MAC}")

# Test different configurations - start with configured port
configs = [
    {"port": int(FRITZ_PORT), "tls": True, "name": f"Configured Port ({FRITZ_PORT}) HTTPS"},
    {"port": int(FRITZ_PORT), "tls": False, "name": f"Configured Port ({FRITZ_PORT}) HTTP"},
    {"port": 49443, "tls": True, "name": "Standard HTTPS (49443)"},
    {"port": 443, "tls": True, "name": "HTTPS (443)"},
    {"port": 49000, "tls": False, "name": "HTTP (49000)"},
    {"port": 80, "tls": False, "name": "HTTP (80)"},
]

for config in configs:
    print(f"\n=== Testing {config['name']} ===")
    try:
        fc = FritzConnection(
            address=FRITZ_IP,
            port=config['port'],
            user=FRITZ_USER.strip('"'),  # Remove quotes from username
            password=FRITZ_PASSWORD.strip('"'),  # Remove quotes from password
            use_tls=config['tls']
        )
        print("✅ Connection successful")

        # Test getting device info
        device_info = fc.call_action("DeviceInfo", "GetInfo")
        print(f"✅ Device info retrieved: {device_info.get('NewModelName', 'Unknown')}")

        # Test Wake-on-LAN
        if 'X_AVM-DE_Homeauto' in fc.services:
            result = fc.call_action(
                "X_AVM-DE_Homeauto",
                "WakeOnLANByMACAddress",
                MACAddress=SERVER_MAC
            )
            print(f"✅ Wake-on-LAN successful: {result}")
        else:
            print("❌ Wake-on-LAN service not available")

        break  # Stop at first working config

    except Exception as e:
        print(f"❌ Failed: {e}")

print("\n=== Manual Check ===")
print("Please check in your FritzBox:")
print("1. System > FritzBox-Benutzer > TR-064 aktivieren")
print("2. Internet > Freigaben > Port-Freigaben für TR-064")
print("3. Correct username (without spaces):", repr(FRITZ_USER.strip('"')))
print("4. Correct DynDNS address:", FRITZ_IP)