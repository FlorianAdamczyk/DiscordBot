# Discord FritzBox Bot

Ein schlanker Discord-Bot zum Starten eines Servers über Wake-on-LAN per FritzBox. Der Bot verwendet den TR-064-Standard, um direkt mit der FritzBox zu kommunizieren und ein Magic Packet zu senden.

Die README ist auf Deutsch verfasst und erklärt, wie du das Projekt lokal betreibst und auf Render.com deployst.

**Wichtig**: Bewahre alle Tokens und Secrets in deiner lokalen `.env` Datei sicher auf. Vermeide das Einchecken von echten Tokens in ein öffentliches Repo.

---

## Projektüberblick

Dieser Bot bietet:

- **Slash-Befehl `/bootserver`**: Sendet ein Wake-on-LAN Magic Packet über die FritzBox an den Server
- **FritzBox TR-064 Integration**: Nutzt den offiziellen TR-064-Standard für sichere HTTPS-Kommunikation
- **Minimaler Code**: Nur das Nötigste für die WOL-Funktionalität
- **Flask Webserver**: Für Hosting-Plattformen wie Render.com, die einen Healthcheck-Endpoint benötigen

---

## Voraussetzungen

### Technische Anforderungen
- Python 3.10+ (oder eine aktuelle 3.x Version)
- Ein Discord Bot Token mit Intent `message_content` aktiviert
- Eine FritzBox mit:
  - TR-064 über HTTPS aktiviert
  - Einem konfigurierten Benutzer für den Bot
  - Wake-on-LAN Unterstützung
- Die MAC-Adresse des zu startenden Servers

### FritzBox Konfiguration

1. **TR-064 aktivieren**:
   - Öffne die FritzBox-Oberfläche (z.B. `fritz.box` oder `192.168.178.1`)
   - Gehe zu: **Heimnetz** → **Netzwerk** → **Netzwerkeinstellungen**
   - Aktiviere: **Zugriff für Anwendungen zulassen** (TR-064-Protokoll über HTTPS)

2. **Benutzer anlegen**:
   - Gehe zu: **System** → **FRITZ!Box-Benutzer**
   - Klicke auf **Benutzer hinzufügen**
   - Name: `discordbot` (oder ein anderer Name)
   - Passwort: Ein starkes, langes Passwort
   - Rechte: **FRITZ!Box Einstellungen**

3. **DynDNS einrichten** (optional, aber empfohlen):
   - Gehe zu: **Internet** → **Freigaben** → **DynDNS**
   - Konfiguriere einen DynDNS-Dienst (z.B. `meinserver.ddns.net`)
   - Dies ermöglicht den Zugriff von außen

4. **MAC-Adresse ermitteln**:
   - Windows: `ipconfig /all` → "Physische Adresse"
   - Linux/Mac: `ip link` oder `ifconfig` → "ether" oder "HWaddr"
   - Format: `AA:BB:CC:DD:EE:FF`

---

## Installation & lokale Ausführung

1. **Repository klonen** oder in dein Projektverzeichnis navigieren

2. **Virtuelles Environment erstellen und Abhängigkeiten installieren**

   PowerShell (Windows):
   ```pwsh
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

   Bash (Linux/Mac):
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **`.env` Datei erstellen**

   Kopiere `.env.example` zu `.env` und fülle die Werte aus:
   ```
   DISCORD_TOKEN=dein_discord_bot_token
   FRITZ_IP=meinserver.ddns.net
   FRITZ_USER=discordbot
   FRITZ_PASSWORD=dein_fritzbox_passwort
   SERVER_MAC=AA:BB:CC:DD:EE:FF
   FRITZ_PORT=44443
   ```

4. **Bot starten**

   ```pwsh
   python main.py
   ```

   Der Bot sollte sich bei Discord einloggen und die Slash-Commands synchronisieren.

---

## Konfiguration (`.env`)

| Variable | Beschreibung | Beispiel |
|----------|--------------|----------|
| `DISCORD_TOKEN` | Dein Discord Bot Token | `MTA1Nz...` |
| `FRITZ_IP` | FritzBox IP oder DynDNS-Adresse | `meinserver.ddns.net` |
| `FRITZ_USER` | FritzBox-Benutzername | `discordbot` |
| `FRITZ_PASSWORD` | FritzBox-Passwort | `MeinSicheresPasswort123!` |
| `SERVER_MAC` | MAC-Adresse des Servers | `AA:BB:CC:DD:EE:FF` |
| `FRITZ_PORT` | HTTPS-Port der FritzBox | `44443` (Standard) |
| `LOG_LEVEL` | Logging-Level (optional) | `INFO` oder `DEBUG` |
| `PORT` | Flask Webserver Port (optional) | `10000` |

---

## Bereitstellung auf Render.com

1. **Erstelle einen neuen Web Service** auf [Render.com](https://render.com)

2. **Verbinde dein GitHub Repository**

3. **Konfiguration**:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python main.py`
   - **Environment**: `Python 3`

4. **Environment Variables** hinzufügen:
   - Füge alle Werte aus deiner `.env` Datei als Environment Variables hinzu
   - Render verschlüsselt diese automatisch

5. **Deploy**: Render startet automatisch den Build und Deploy-Prozess

Der Flask-Webserver läuft auf Port 10000 (oder dem von Render zugewiesenen Port) und beantwortet Healthchecks.

---

## Benutzung & Verhalten des Bots

### `/bootserver` Befehl

1. Benutzer gibt `/bootserver` in Discord ein
2. Bot antwortet: "🔍 Versuche FritzBox zu erreichen..."
3. Bot verbindet sich zur FritzBox über HTTPS
4. Bot authentifiziert sich mit Benutzername und Passwort
5. Bot sendet Wake-on-LAN Befehl mit der konfigurierten MAC-Adresse
6. Bei Erfolg: "✅ Magic Packet gesendet! Server fährt hoch. Bitte 2 Min warten."
7. Bei Fehler: Fehlermeldung mit Details

### Was passiert im Hintergrund?

1. **SSL-Verbindung**: Der Bot nutzt HTTPS (Port 44443) für sichere Kommunikation
2. **TR-064 Protokoll**: Standard-Schnittstelle für FritzBox-Steuerung
3. **Wake-on-LAN**: Die FritzBox sendet ein Magic Packet an die angegebene MAC-Adresse
4. **Server startet**: Der Server (falls WOL im BIOS aktiviert ist) fährt hoch

---

## Fehlerbehebung

### Bot kann FritzBox nicht erreichen

- **Prüfe die IP/DynDNS**: Ist `FRITZ_IP` korrekt?
- **Prüfe den Port**: Standard ist `44443` für HTTPS
- **Firewall**: Ist der Port von außen erreichbar? (Falls der Bot extern läuft)
- **TR-064 aktiviert**: Siehe "FritzBox Konfiguration" oben

### "Authentication failed" oder ähnliche Fehler

- **Benutzername/Passwort**: Sind `FRITZ_USER` und `FRITZ_PASSWORD` korrekt?
- **Benutzerrechte**: Hat der Benutzer die richtigen Rechte in der FritzBox?
- **Passwort-Sonderzeichen**: Manche Sonderzeichen können Probleme machen - teste mit alphanumerischem Passwort

### Server startet nicht

- **Wake-on-LAN aktiviert**: Im BIOS/UEFI des Servers muss WOL aktiviert sein
- **Netzwerkkabel**: WOL funktioniert meist nur über Kabel, nicht über WLAN
- **MAC-Adresse**: Ist die MAC-Adresse korrekt? (Groß-/Kleinschreibung egal)
- **Netzwerk**: Ist der Server im gleichen Netzwerk wie die FritzBox?

### Bot startet nicht

- **Dependencies**: `pip install -r requirements.txt` ausführen
- **Python-Version**: Mindestens Python 3.10
- **Environment Variables**: Alle erforderlichen Variablen gesetzt?
- **Discord Token**: Ist der Token gültig und der Bot in deinem Server?

### Slash-Command wird nicht angezeigt

- **Berechtigungen**: Hat der Bot die `applications.commands` Berechtigung?
- **Synchronisation**: Warte ein paar Minuten - Discord kann bis zu einer Stunde brauchen
- **Bot Invite**: Wurde der Bot mit dem richtigen Scope eingeladen? (`bot` + `applications.commands`)

---

## Sicherheitshinweise

- **Niemals** Passwörter oder Tokens im Code oder in öffentlichen Repos speichern
- Nutze `.env` Dateien für lokale Entwicklung
- Auf Hosting-Plattformen: Environment Variables verwenden
- `.env` sollte in `.gitignore` stehen (ist bereits enthalten)
- FritzBox-Benutzer mit minimalen Rechten anlegen
- HTTPS (nicht HTTP) für FritzBox-Verbindung verwenden
- Regelmäßig Passwörter ändern

---

## Dependencies

- **discord.py**: Discord Bot Framework
- **python-dotenv**: Environment Variables laden
- **flask**: Webserver für Healthchecks
- **fritzconnection**: FritzBox TR-064 Bibliothek

Siehe `requirements.txt` für genaue Versionen.

---

## Lizenz

Dieses Projekt ist für private Nutzung gedacht. Siehe LICENSE Datei (falls vorhanden).

---

## Support

Bei Fragen oder Problemen:
1. Prüfe die Fehlerbehebung oben
2. Schaue in die Logs (`LOG_LEVEL=DEBUG` in `.env` setzen)
3. Prüfe die FritzBox-Einstellungen
4. Erstelle ein GitHub Issue mit detaillierten Informationen

---

**Viel Erfolg mit deinem Discord FritzBox Bot!** 🚀
