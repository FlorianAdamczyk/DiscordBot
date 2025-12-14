import logging
import os
import threading
import time
from datetime import datetime, timedelta

import discord
from discord.ext import commands
from dotenv import load_dotenv
from flask import Flask
import requests
from bs4 import BeautifulSoup
import urllib3

load_dotenv()

# Environment Variables
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", "0"))
DISCORD_ANNOUNCE_CHANNEL_ID = int(os.getenv("DISCORD_ANNOUNCE_CHANNEL_ID", "0"))
FRITZ_URL = os.getenv("FRITZ_URL")  # Komplette URL mit Port, z.B. https://xyz.myfritz.net:41284
FRITZ_USER = os.getenv("FRITZ_USER")
FRITZ_PASSWORD = os.getenv("FRITZ_PASSWORD")
SERVER_MAC = os.getenv("SERVER_MAC")
ALLOWED_USER_IDS = os.getenv("ALLOWED_USER_IDS", "")  # Komma-getrennt, z.B. "123,456,789"
ALLOWED_ROLE_IDS = os.getenv("ALLOWED_ROLE_IDS", "")  # Komma-getrennt
COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", "120"))  # 2 Minuten Standard

# Validierung der Environment Variables
if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN must be set in the environment or .env file.")
if not FRITZ_URL or not FRITZ_USER or not FRITZ_PASSWORD or not SERVER_MAC:
    raise RuntimeError("FritzBox credentials (FRITZ_URL, FRITZ_USER, FRITZ_PASSWORD, SERVER_MAC) must be configured.")

# Parse allowed users/roles
ALLOWED_USERS = [int(x.strip()) for x in ALLOWED_USER_IDS.split(",") if x.strip().isdigit()]
ALLOWED_ROLES = [int(x.strip()) for x in ALLOWED_ROLE_IDS.split(",") if x.strip().isdigit()]

# SSL-Warnungen unterdrücken (für selbstsignierte FRITZ!Box-Zertifikate)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
logger = logging.getLogger("discordbot")

# Flask Web Server (für Render oder andere Hosting-Plattformen)
app = Flask(__name__)

# Cooldown-Tracking
last_bootserver_time = None
cooldown_lock = threading.Lock()


@app.get("/")
def home() -> tuple[str, int]:
    return "✅ Ich bin bereit und warte auf deinen /bootserver Befehl!", 200


def run_web() -> None:
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)


threading.Thread(target=run_web, name="FlaskThread", daemon=True).start()


def send_wol_via_fritzbox(fritz_url: str, username: str, password: str, mac_address: str) -> dict:
    """
    Sendet ein Wake-on-LAN-Paket über die FRITZ!Box-Weboberfläche.
    
    Returns:
        dict mit 'success' (bool) und 'message' (str)
    """
    session = requests.Session()
    session.verify = False  # Selbstsigniertes Zertifikat
    
    try:
        # Schritt 1: Login-Seite aufrufen und SID holen
        login_url = f"{fritz_url}/login_sid.lua?version=2"
        response = session.get(login_url, timeout=15)
        
        if response.status_code != 200:
            return {"success": False, "message": f"FRITZ!Box Login-Seite nicht erreichbar (HTTP {response.status_code})"}
        
        # Parse Challenge
        soup = BeautifulSoup(response.text, 'html.parser')
        challenge = soup.find('challenge')
        if not challenge:
            return {"success": False, "message": "Kein Challenge-Token gefunden - ist die FRITZ!Box-URL korrekt?"}
        
        challenge_text = challenge.text
        
        # Schritt 2: Response berechnen (MD5-basiert)
        import hashlib
        challenge_response = challenge_text + "-" + hashlib.md5(
            f"{challenge_text}-{password}".encode('utf-16le')
        ).hexdigest()
        
        # Schritt 3: Login durchführen
        login_params = {
            "username": username,
            "response": challenge_response
        }
        response = session.get(login_url, params=login_params, timeout=15)
        
        if response.status_code != 200:
            return {"success": False, "message": f"Login-Anfrage fehlgeschlagen (HTTP {response.status_code})"}
        
        # Parse SID
        soup = BeautifulSoup(response.text, 'html.parser')
        sid_tag = soup.find('sid')
        if not sid_tag or sid_tag.text == "0000000000000000":
            return {"success": False, "message": "Login fehlgeschlagen - Benutzername oder Passwort falsch, oder Benutzer hat keine Internet-Zugangsrechte"}
        
        sid = sid_tag.text
        logger.info(f"FRITZ!Box Login erfolgreich, SID: {sid[:8]}...")
        
        # Schritt 4: Wake-on-LAN auslösen über die richtige URL
        # Normalisiere MAC-Adresse (entferne : und -)
        mac_clean = mac_address.replace(":", "").replace("-", "").upper()
        
        # FRITZ!Box WOL-URL (kann je nach Modell variieren)
        wol_url = f"{fritz_url}/data.lua"
        wol_params = {
            "sid": sid,
            "page": "netDev",
            "xhrId": "wakeup",
            "wake": mac_clean
        }
        
        response = session.get(wol_url, params=wol_params, timeout=15)
        
        if response.status_code == 200:
            logger.info(f"Wake-on-LAN für MAC {mac_address} gesendet")
            return {"success": True, "message": "Magic Packet erfolgreich gesendet!"}
        else:
            return {"success": False, "message": f"WOL-Anfrage fehlgeschlagen (HTTP {response.status_code})"}
            
    except requests.exceptions.Timeout:
        return {"success": False, "message": "Timeout - FRITZ!Box nicht erreichbar (ist die URL korrekt?)"}
    except requests.exceptions.ConnectionError:
        return {"success": False, "message": "Verbindungsfehler - FRITZ!Box nicht erreichbar"}
    except Exception as e:
        logger.error(f"Fehler bei FRITZ!Box-Kommunikation: {e}", exc_info=True)
        return {"success": False, "message": f"Unerwarteter Fehler: {str(e)}"}
    finally:
        session.close()


def check_permissions(interaction: discord.Interaction) -> tuple[bool, str]:
    """
    Prüft, ob der User berechtigt ist, /bootserver zu nutzen.
    
    Returns:
        (is_allowed, error_message)
    """
    user_id = interaction.user.id
    
    # Wenn keine Whitelist konfiguriert ist, allen erlauben
    if not ALLOWED_USERS and not ALLOWED_ROLES:
        return True, ""
    
    # User-ID-Check
    if ALLOWED_USERS and user_id in ALLOWED_USERS:
        return True, ""
    
    # Role-Check
    if ALLOWED_ROLES and hasattr(interaction.user, 'roles'):
        user_role_ids = [role.id for role in interaction.user.roles]
        if any(role_id in ALLOWED_ROLES for role_id in user_role_ids):
            return True, ""
    
    return False, "❌ Du hast keine Berechtigung, diesen Befehl zu nutzen."


def check_cooldown() -> tuple[bool, int]:
    """
    Prüft, ob der Cooldown abgelaufen ist.
    
    Returns:
        (is_allowed, remaining_seconds)
    """
    global last_bootserver_time
    
    with cooldown_lock:
        if last_bootserver_time is None:
            return True, 0
        
        elapsed = (datetime.now() - last_bootserver_time).total_seconds()
        remaining = COOLDOWN_SECONDS - elapsed
        
        if remaining <= 0:
            return True, 0
        else:
            return False, int(remaining)


def update_cooldown():
    """Aktualisiert den Cooldown-Timer."""
    global last_bootserver_time
    with cooldown_lock:
        last_bootserver_time = datetime.now()


# Discord Bot Setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    """Bot ist bereit und eingeloggt."""
    logger.info(f"Bot eingeloggt als {bot.user}")
    await bot.change_presence(activity=discord.Game(name="/bootserver zum Server starten"))
    try:
        if DISCORD_GUILD_ID > 0:
            guild = discord.Object(id=DISCORD_GUILD_ID)
            synced = await bot.tree.sync(guild=guild)
            logger.info(f"{len(synced)} Slash Commands für Guild {DISCORD_GUILD_ID} synchronisiert")
        else:
            synced = await bot.tree.sync()
            logger.info(f"{len(synced)} Slash Commands global synchronisiert")
    except Exception as e:
        logger.error(f"Fehler beim Synchronisieren der Commands: {e}")


@bot.tree.command(name="bootserver", description="Startet den Server über FritzBox Wake-on-LAN")
async def bootserver(interaction: discord.Interaction):
    """
    Slash Command: /bootserver
    Sendet ein Magic Packet über die FritzBox, um den Server zu starten.
    """
    # Berechtigungsprüfung
    is_allowed, error_msg = check_permissions(interaction)
    if not is_allowed:
        await interaction.response.send_message(error_msg, ephemeral=True)
        logger.warning(f"Unberechtigter Zugriff von User {interaction.user} (ID: {interaction.user.id})")
        return
    
    # Cooldown-Prüfung
    cooldown_ok, remaining = check_cooldown()
    if not cooldown_ok:
        await interaction.response.send_message(
            f"⏱️ Bitte warte noch {remaining} Sekunden, bevor du den Befehl erneut nutzt.",
            ephemeral=True
        )
        return
    
    await interaction.response.defer()
    
    try:
        # Status-Update
        await interaction.followup.send("🔍 Verbinde mit FRITZ!Box...")
        logger.info(f"User {interaction.user} startet Server via {FRITZ_URL}")
        
        # Benutzername und Passwort ohne Anführungszeichen
        fritz_user = FRITZ_USER.strip('"') if FRITZ_USER else FRITZ_USER
        fritz_password = FRITZ_PASSWORD.strip('"') if FRITZ_PASSWORD else FRITZ_PASSWORD
        
        # Wake-on-LAN über FRITZ!Box senden
        result = send_wol_via_fritzbox(FRITZ_URL, fritz_user, fritz_password, SERVER_MAC)
        
        if result["success"]:
            # Erfolg!
            success_message = f"✅ {result['message']}\nServer fährt hoch. Bitte 2-3 Min warten."
            await interaction.followup.send(success_message)
            
            # Cooldown aktualisieren
            update_cooldown()
            
            # Optionale Ankündigung im Channel
            if DISCORD_ANNOUNCE_CHANNEL_ID > 0:
                try:
                    channel = bot.get_channel(DISCORD_ANNOUNCE_CHANNEL_ID)
                    if channel:
                        await channel.send(
                            f"🚀 **Server wird hochgefahren!**\n"
                            f"Gestartet von {interaction.user.mention}"
                        )
                        logger.info(f"Ankündigung an Channel {DISCORD_ANNOUNCE_CHANNEL_ID} gesendet")
                except Exception as e:
                    logger.warning(f"Fehler beim Senden der Ankündigung: {e}")
        else:
            # Fehler
            error_message = f"❌ {result['message']}"
            await interaction.followup.send(error_message)
            logger.error(f"WOL fehlgeschlagen: {result['message']}")
        
    except Exception as e:
        # Unerwarteter Fehler
        error_msg = f"❌ Unerwarteter Fehler: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await interaction.followup.send(error_msg)


def main():
    """Startet den Discord Bot."""
    logger.info("Starte Discord Bot...")
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
