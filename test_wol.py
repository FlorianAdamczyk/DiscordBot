import os
from dotenv import load_dotenv
import sys

# Füge den Hauptordner zum Path hinzu
sys.path.insert(0, os.path.dirname(__file__))

# Importiere die WOL-Funktion aus main.py
load_dotenv()
from main import send_wol_via_fritzbox

FRITZ_URL = os.getenv("FRITZ_URL")
FRITZ_USER = os.getenv("FRITZ_USER")
FRITZ_PASSWORD = os.getenv("FRITZ_PASSWORD")
SERVER_MAC = os.getenv("SERVER_MAC")

print(f"Testing FRITZ!Box WOL Function")
print(f"URL: {FRITZ_URL}")
print(f"User: {FRITZ_USER}")
print(f"MAC: {SERVER_MAC}")
print()

print("Sending Wake-on-LAN...")
result = send_wol_via_fritzbox(FRITZ_URL, FRITZ_USER, FRITZ_PASSWORD, SERVER_MAC)

print()
print(f"Success: {result['success']}")
print(f"Message: {result['message']}")
