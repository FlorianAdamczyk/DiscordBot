import logging
import os
import threading
import time
from datetime import datetime, timedelta
import asyncio

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
    Simuliert einen Browser-Login und klickt den "Aufwecken"-Button.
    
    Returns:
        dict mit 'success' (bool) und 'message' (str)
    """
    session = requests.Session()
    session.verify = False  # Selbstsigniertes Zertifikat
    
    # Browser-Headers simulieren
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'de,en-US;q=0.7,en;q=0.3',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    })
    
    try:
        # Schritt 1: Hauptseite aufrufen (etabliert Session)
        logger.info(f"Verbinde zu FRITZ!Box: {fritz_url}")
        response = session.get(fritz_url, timeout=15, allow_redirects=True)
        
        if response.status_code != 200:
            return {"success": False, "message": f"FRITZ!Box nicht erreichbar (HTTP {response.status_code})"}
        
        # Schritt 2: Challenge für Login holen
        import hashlib
        import xml.etree.ElementTree as ET
        
        login_url = f"{fritz_url}/login_sid.lua"
        response = session.get(login_url, timeout=15)
        
        if response.status_code != 200:
            return {"success": False, "message": f"Login-Seite nicht erreichbar (HTTP {response.status_code})"}
        
        # Parse XML response
        try:
            root = ET.fromstring(response.text)
            challenge = root.find('Challenge').text
            sid = root.find('SID').text
            block_time = root.find('BlockTime').text
            
            if int(block_time) > 0:
                return {"success": False, "message": f"Account ist für {block_time} Sekunden gesperrt"}
            
            # Check if already logged in
            if sid != "0000000000000000":
                logger.info("Session bereits aktiv, nutze bestehende SID")
            else:
                # Schritt 3: Response berechnen (MD5-Challenge-Response-Verfahren)
                # Format: challenge + "-" + MD5(challenge + "-" + password)
                # Password muss als UTF-16LE kodiert werden
                challenge_password = f"{challenge}-{password}"
                md5_hash = hashlib.md5(challenge_password.encode('utf-16le')).hexdigest()
                response_str = f"{challenge}-{md5_hash}"
                
                # Schritt 4: Login durchführen
                login_params = {
                    "username": username,
                    "response": response_str
                }
                response = session.get(login_url, params=login_params, timeout=15)
                
                if response.status_code != 200:
                    return {"success": False, "message": f"Login fehlgeschlagen (HTTP {response.status_code})"}
                
                # Parse SID
                root = ET.fromstring(response.text)
                sid = root.find('SID').text
                
                if sid == "0000000000000000":
                    return {"success": False, "message": "Login fehlgeschlagen - Benutzername oder Passwort falsch"}
                
                logger.info(f"FRITZ!Box Login erfolgreich, SID: {sid[:8]}...")
        
        except Exception as e:
            return {"success": False, "message": f"XML-Parsing fehlgeschlagen: {str(e)}"}
        
        # Schritt 5: UID des Zielgeräts ermitteln (netDev -> devices)
        # Wichtig: bei Zugriff über myfritz.net sind viele alte *.lua-Pfade 404.
        # Referer daher auf eine existierende Seite setzen.
        session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{fritz_url}/",
            "Origin": fritz_url,
        })
        devices_resp = session.post(
            f"{fritz_url}/data.lua",
            data={"sid": sid, "xhr": "1", "page": "netDev", "xhrId": "devices"},
            timeout=15,
        )
        if devices_resp.status_code != 200:
            return {"success": False, "message": f"Geräteliste nicht abrufbar (HTTP {devices_resp.status_code})"}
        
        uid = None
        try:
            data_json = devices_resp.json()
            active = data_json.get("data", {}).get("active", [])
            passive = data_json.get("data", {}).get("passive", [])
            target_mac = mac_address.upper()
            for dev in active + passive:
                if dev.get("mac", "").upper() == target_mac:
                    uid = dev.get("UID")
                    break
        except Exception as ex:
            logger.debug(f"Parsing Geräte-JSON fehlgeschlagen: {ex}")
        
        if not uid:
            return {
                "success": False,
                "message": "Geräte-UID nicht gefunden – ist die MAC korrekt und ist das Gerät in der FRITZ!Box-Liste vorhanden?",
            }
        
        # Schritt 6: Wake-on-LAN über UID auslösen
        # Wir senden die gleiche XHR-Form wie die Weboberfläche. Einige FRITZ!OS-Versionen
        # erwarten zusätzlich ein "lang"-Feld.
        wol_url = f"{fritz_url}/data.lua"
        wol_params = {
            "sid": sid,
            "xhr": "1",
            "lang": "de",
            "page": "netDev",
            "xhrId": "wakeup",
            "dev": uid,
        }

        # Manche Boxen reagieren zickig; 2 schnelle Versuche erhöhen die Chance,
        # dass der Aufweck-Request akzeptiert wird.
        last_status = None
        last_text = ""
        for attempt in (1, 2):
            try:
                response = session.post(wol_url, data=wol_params, timeout=12)
                last_status = response.status_code
                last_text = response.text or ""

                # Plausibilitätscheck: wir erwarten JSON mit pid=netDev
                ok = False
                if response.status_code == 200:
                    try:
                        js = response.json()
                        ok = js.get("pid") == "netDev"
                    except Exception:
                        ok = "error" not in last_text.lower()

                logger.info(
                    f"Wake-on-LAN Request (attempt {attempt}) via UID {uid} gesendet (Status: {response.status_code})"
                )

                if ok:
                    return {"success": True, "message": "Magic Packet erfolgreich gesendet!"}

                time.sleep(0.4)
            except requests.exceptions.Timeout:
                # Timeout ist nicht zwingend ein Erfolg; aber bei manchen Boxen kommt die Antwort spät.
                logger.info(f"Wake-on-LAN Request (attempt {attempt}) Timeout – wiederhole ggf.")
                time.sleep(0.4)
                continue

        return {
            "success": False,
            "message": f"WOL-Request wurde gesendet, aber keine gültige Bestätigung erhalten (HTTP {last_status}).",
        }
            
    except requests.exceptions.Timeout:
        return {"success": False, "message": "Timeout - FRITZ!Box nicht erreichbar (ist die URL korrekt?)"}
    except requests.exceptions.ConnectionError as e:
        return {"success": False, "message": f"Verbindungsfehler - FRITZ!Box nicht erreichbar: {str(e)[:100]}"}
    except Exception as e:
        logger.error(f"Fehler bei FRITZ!Box-Kommunikation: {e}", exc_info=True)
        return {"success": False, "message": f"Unerwarteter Fehler: {str(e)[:200]}"}
    finally:
        session.close()


def _fritz_login_and_get_sid(session: requests.Session, fritz_url: str, username: str, password: str) -> str:
    import hashlib
    import xml.etree.ElementTree as ET

    login_url = f"{fritz_url}/login_sid.lua"
    response = session.get(login_url, timeout=15)
    response.raise_for_status()

    root = ET.fromstring(response.text)
    challenge = root.find('Challenge').text
    sid = root.find('SID').text
    block_time = root.find('BlockTime').text
    if int(block_time) > 0:
        raise RuntimeError(f"Account ist für {block_time} Sekunden gesperrt")

    if sid != "0000000000000000":
        return sid

    challenge_password = f"{challenge}-{password}"
    md5_hash = hashlib.md5(challenge_password.encode('utf-16le')).hexdigest()
    response_str = f"{challenge}-{md5_hash}"

    response = session.get(login_url, params={"username": username, "response": response_str}, timeout=15)
    response.raise_for_status()

    root = ET.fromstring(response.text)
    sid = root.find('SID').text
    if sid == "0000000000000000":
        raise RuntimeError("Login fehlgeschlagen (SID=0)")
    return sid


def _fritz_fetch_netdev_devices(session: requests.Session, fritz_url: str, sid: str) -> dict:
    session.headers.update({
        "Accept": "application/json, text/plain, */*",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{fritz_url}/",
        "Origin": fritz_url,
    })
    resp = session.post(
        f"{fritz_url}/data.lua",
        data={"sid": sid, "xhr": "1", "page": "netDev", "xhrId": "devices"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def _fritz_find_device_by_mac(devices_json: dict, mac_address: str) -> tuple[str | None, str | None, bool | None]:
    target_mac = mac_address.upper()
    data = devices_json.get("data", {})
    for dev in (data.get("active", []) + data.get("passive", [])):
        if dev.get("mac", "").upper() == target_mac:
            uid = dev.get("UID")
            name = dev.get("name")
            state_class = None
            state = dev.get("state")
            if isinstance(state, dict):
                state_class = state.get("class")
            is_online = state_class == "globe_online"
            return uid, name, is_online
    return None, None, None


def confirm_device_online_via_fritzbox(
    fritz_url: str,
    username: str,
    password: str,
    mac_address: str,
    wait_seconds: int = 150,
    poll_interval: int = 10,
) -> dict:
    """Pollt die FRITZ!Box netDev-Geräteliste und prüft, ob das Gerät online wird."""
    session = requests.Session()
    session.verify = False
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'de,en-US;q=0.7,en;q=0.3',
        'Connection': 'keep-alive',
    })
    try:
        sid = _fritz_login_and_get_sid(session, fritz_url, username, password)

        deadline = time.monotonic() + max(0, wait_seconds)
        last_seen_name = None
        last_seen_uid = None
        last_seen_online = None

        while True:
            devices_json = _fritz_fetch_netdev_devices(session, fritz_url, sid)
            uid, name, is_online = _fritz_find_device_by_mac(devices_json, mac_address)
            last_seen_name, last_seen_uid, last_seen_online = name, uid, is_online

            if is_online:
                return {
                    "success": True,
                    "message": "Gerät ist online.",
                    "uid": uid,
                    "name": name,
                }

            if time.monotonic() >= deadline:
                return {
                    "success": False,
                    "message": "Gerät bleibt offline (FRITZ!Box meldet es weiterhin getrennt).",
                    "uid": uid,
                    "name": name,
                    "online": last_seen_online,
                }

            time.sleep(max(1, poll_interval))
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
    await bot.change_presence(activity=discord.Game(name="/bootserver tippen"))
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
        
        # Wake-on-LAN über FRITZ!Box senden (blocking -> Thread)
        result = await asyncio.to_thread(send_wol_via_fritzbox, FRITZ_URL, fritz_user, fritz_password, SERVER_MAC)
        
        if result["success"]:
            await interaction.followup.send(f"✅ {result['message']}\n🔎 Prüfe, ob der Server online geht ...")

            # Verifikation: wird das Gerät wirklich online?
            verify = await asyncio.to_thread(
                confirm_device_online_via_fritzbox,
                FRITZ_URL,
                fritz_user,
                fritz_password,
                SERVER_MAC,
                150,
                10,
            )

            if verify.get("success"):
                await interaction.followup.send("🚀 Server ist online (FRITZ!Box meldet Verbindung aktiv).")
            else:
                await interaction.followup.send(
                    "⚠️ Wake wurde gesendet, aber die FRITZ!Box sieht den Server weiterhin offline.\n"
                    "Wenn der manuelle Button funktioniert, poste bitte einmal den Browser-Network-Request von 'Gerät starten' (Copy as cURL), dann matchen wir ihn 1:1."
                )
            
            # Cooldown aktualisieren
            update_cooldown()
            
            # Cooldown aktualisieren
            update_cooldown()

            # Optionale Ankündigung im Channel nur bei bestätigtem Online-Status
            if verify.get("success") and DISCORD_ANNOUNCE_CHANNEL_ID > 0:
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
