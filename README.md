# Discord Tuya Bot

Ein schlanker Discord-Bot zum Ein- und Ausschalten einer Tuya‑Smart‑Plug (z. B. um einen Server zu booten oder abzuschalten). Dieses Repository enthält eine Render-freundliche Web-Heartbeat-Route (Flask), eine schlanke Tuya‑API‑Integration und einen Discord-Slash-Befehl `/bootserver`.

Die README ist auf Deutsch verfasst und erklärt, wie du das Projekt lokal betreibst und auf Render.com deployst.

**Wichtig**: Bewahre alle Tokens und Secrets in deiner lokalen `.env` Datei sicher auf. Vermeide das Einchecken von echten Tokens in ein öffentliches Repo.

**Inhalt dieser Datei**
- Projektüberblick
- Voraussetzungen
- Installation & lokale Ausführung
- Konfiguration (`.env`)
- Bereitstellung auf Render.com
- Benutzung & Verhalten des Bots
- Fehlerbehebung
- Sicherheitshinweise

---

## Projektüberblick

Dieser Bot bietet:

- Slash‑Befehl `/bootserver` um eine Tuya‑Smart‑Plug einzuschalten (Server booten).
- Wenn die Bot‑Instanz selbst eine Nachricht sendet, die die Phrase
  "Speichern & Herunterfahren wird eingeleitet." enthält, startet ein 3‑Minuten‑Countdown.
- Wenn innerhalb der 3 Minuten keine bestätigende Nachricht "Server läuft, und ist Online."
  gesendet wird, schaltet der Bot die Steckdose aus.
- Minimaler, stabiler Code: kein komplexes Power‑Monitoring mehr, stattdessen ein robustes Countdown‑Verhalten.

Die kleine Flask‑App sorgt dafür, dass Render (oder ähnliche Plattformen) eine Web‑Route
zum Healthcheck hat (Port muss geöffnet sein).

## Voraussetzungen

- Python 3.10+ (oder eine aktuelle 3.x Version)
- Ein Discord Bot Token mit Intent `message_content` aktiviert
- Tuya Developer Zugang (Client ID / Client Secret) und Device ID der smarten Steckdose
- `requirements.txt` enthält die Abhängigkeiten (`discord.py`, `httpx`, `python-dotenv`, `flask`)

## Installation & lokale Ausführung

1. Klone das Repository oder navigiere in dein Projektverzeichnis.
2. Erstelle ein virtuelles Environment und installiere Abhängigkeiten.

PowerShell (empfohlen auf Windows):

```pwsh
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

3. Lege eine `.env` Datei an (siehe Abschnitt Konfiguration).
4. Starte den Bot lokal (dies startet auch den kleinen Flask‑Webserver auf `PORT`):

```pwsh
python main.py
```

Beachte: Der Bot loggt Statusmeldungen in die Konsole. Die Flask‑App läuft in einem Hintergrund‑Thread
und antwortet auf `/` mit einem kurzen Text für Healthchecks.

## Konfiguration (`.env`)

Lege eine `.env` Datei im Projektordner an (oder passe die vorhandene an). Die `main.py` liest diese Variablen:

- `DISCORD_TOKEN` — Discord Bot Token (z. B. `MT...`)
- `DISCORD_GUILD_ID` — (optional, empfohlen) ID deines Servers (Guild) für schnelle, guild‑spezifische Slash‑Kommando‑Registrierung
- `TUYA_CLIENT_ID` — Tuya API Client ID
- `TUYA_CLIENT_SECRET` — Tuya API Client Secret
- `TUYA_DEVICE_ID` — Device ID der smarten Steckdose
- `DISCORD_ANNOUNCE_CHANNEL_ID` — (optional) Kanal‑ID, in den der Bot systemseitig Nachrichten posten darf
- `PORT` — (optional) Port für die Flask Health‑Route (Render nutzt standardmäßig die Umgebungsvariable `PORT`)

Beispiel `.env` (niemals echte Tokens in ein öffentliches Repo committen):

```ini
DISCORD_TOKEN="your_discord_token_here"
DISCORD_GUILD_ID=123456789012345678
TUYA_CLIENT_ID="..."
TUYA_CLIENT_SECRET="..."
TUYA_DEVICE_ID="..."
DISCORD_ANNOUNCE_CHANNEL_ID=123456789012345678
PORT=10000
```

## Deploy auf Render.com

Render erwartet, dass ein Web‑Prozess auf dem von Render gesetzten `PORT` lauscht. Die App startet lokal eine kleine Flask‑App, die genau das macht.

Schritte (Kurzfassung):

1. Neues Web Service auf Render anlegen.
2. Repo verbinden (GitHub/GitLab).
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `python main.py`
5. Setze Secrets/Environment Variables im Render Dashboard (DISCORD_TOKEN, TUYA_..., DISCORD_GUILD_ID, etc.).

Wichtig: Render setzt die Umgebungsvariable `PORT` automatisch; die Flask‑App in `main.py` liest diese Variable.

## Nutzung & Verhalten

- Slash‑Kommando `/bootserver`: Schaltet die konfigurierte Tuya‑Steckdose ein. Wenn bereits an, antwortet der Bot mit einer freundlichen Meldung.
- Shutdown‑Trigger: Wenn der Bot selbst (oder ein anderes Script mit dem Bot) eine Nachricht sendet, die die Phrase
  "Speichern & Herunterfahren wird eingeleitet." enthält, startet ein 3‑Minuten‑Countdown (nur wenn der Plug an ist).
- Bestätigung: Wird innerhalb der 3 Minuten eine Nachricht mit exakt `Server läuft, und ist Online.` gepostet,
  wird der Countdown abgebrochen.
- Timeout: Erfolgt keine Bestätigung, schaltet der Bot die Steckdose aus und postet eine kurze, entspannte Meldung.

Hinweis zur Slash‑Kommando‑Registrierung:
Wenn du `DISCORD_GUILD_ID` in `.env` setzt, registriert sich `/bootserver` als guild‑lokales Kommando — dadurch ist die Registrierung praktisch sofort sichtbar (statt auf die globale Registration warten zu müssen).

## Beispiele

Booten per Slash:

1. Öffne Discord in deinem Server.
2. Tippe `/bootserver` und bestätige.

Shutdown‑Flow (vereinfachtes Beispiel):

- Ein anderes Script / Service / Bot postet in einem Kanal (oder du postest manuell) eine Nachricht, die die Phrase enthält:
  `... Speichern & Herunterfahren wird eingeleitet. ...`
- Der Bot startet intern einen 3‑Minuten‑Timer.
- Falls innerhalb von 3 Minuten die Nachricht `Server läuft, und ist Online.` gepostet wird, wird der Timer abgebrochen.
- Falls nicht, schaltet der Bot die Steckdose aus und postet: z. B. `🔌 Strom abgestellt – Server gönnt sich eine Pause.`


## Beiträge

Wenn du Verbesserungen vorschlagen willst (z. B. robustere Fehlerroutinen, Tests oder bessere Logging‑Optionen), eröffne bitte einen Pull Request oder Issue im Repository.
