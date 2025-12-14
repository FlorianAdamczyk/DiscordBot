import logging
import os
import threading

import discord
from discord.ext import commands
from dotenv import load_dotenv
from flask import Flask
from fritzconnection import FritzConnection

load_dotenv()

# Environment Variables
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
FRITZ_IP = os.getenv("FRITZ_IP")
FRITZ_USER = os.getenv("FRITZ_USER")
FRITZ_PASSWORD = os.getenv("FRITZ_PASSWORD")
SERVER_MAC = os.getenv("SERVER_MAC")
FRITZ_PORT = os.getenv("FRITZ_PORT", "44443")

# Validierung der Environment Variables
if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN must be set in the environment or .env file.")
if not FRITZ_IP or not FRITZ_USER or not FRITZ_PASSWORD or not SERVER_MAC:
    raise RuntimeError("FritzBox credentials (FRITZ_IP, FRITZ_USER, FRITZ_PASSWORD, SERVER_MAC) must be configured.")

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
logger = logging.getLogger("discordbot")

# Flask Web Server (für Render oder andere Hosting-Plattformen)
app = Flask(__name__)


@app.get("/")
def home() -> tuple[str, int]:
    return "✅ Discord FritzBox Bot is running!", 200


def run_web() -> None:
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)


threading.Thread(target=run_web, name="FlaskThread", daemon=True).start()

# Discord Bot Setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    """Bot ist bereit und eingeloggt."""
    logger.info(f"Bot eingeloggt als {bot.user}")
    await bot.change_presence(activity=discord.Game(name="Warte auf Befehle"))
    try:
        synced = await bot.tree.sync()
        logger.info(f"{len(synced)} Slash Commands synchronisiert")
    except Exception as e:
        logger.error(f"Fehler beim Synchronisieren der Commands: {e}")


@bot.tree.command(name="bootserver", description="Startet den Server über FritzBox Wake-on-LAN")
async def bootserver(interaction: discord.Interaction):
    """
    Slash Command: /bootserver
    Sendet ein Magic Packet über die FritzBox, um den Server zu starten.
    """
    await interaction.response.defer()
    
    try:
        # Schritt 1: Verbindung zur FritzBox herstellen
        await interaction.followup.send("🔍 Versuche FritzBox zu erreichen...")
        logger.info(f"Verbinde zu FritzBox: {FRITZ_IP}:{FRITZ_PORT}")
        
        # FritzConnection mit SSL und Authentifizierung
        fc = FritzConnection(
            address=FRITZ_IP,
            port=int(FRITZ_PORT),
            user=FRITZ_USER,
            password=FRITZ_PASSWORD,
            use_tls=True
        )
        
        # Schritt 2: Wake-on-LAN Service aufrufen
        logger.info(f"Sende Wake-on-LAN für MAC: {SERVER_MAC}")
        
        # TR-064 Service: X_AVM-DE_Host:1
        # Action: WakeOnLANByMACAddress
        result = fc.call_action(
            "X_AVM-DE_Homeauto",  # Service Name
            "WakeOnLANByMACAddress",  # Action Name
            MACAddress=SERVER_MAC
        )
        
        # Schritt 3: Erfolg melden
        logger.info(f"Wake-on-LAN erfolgreich gesendet: {result}")
        await interaction.followup.send(
            "✅ Magic Packet gesendet! Server fährt hoch. Bitte 2 Min warten."
        )
        
    except Exception as e:
        # Fehlerbehandlung
        error_msg = f"❌ Fehler beim Senden des Wake-on-LAN Befehls: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await interaction.followup.send(error_msg)


def main():
    """Startet den Discord Bot."""
    logger.info("Starte Discord Bot...")
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
