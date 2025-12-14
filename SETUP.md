# 🚀 Setup-Anleitung: Discord Bot mit FRITZ!Box Wake-on-LAN

## ✅ Was wurde geändert?

Der Bot nutzt jetzt die **FRITZ!Box-Weboberfläche** statt TR-064:
- ✅ Funktioniert aus der Cloud (Render)
- ✅ Keine offenen Ports nötig (außer dem bestehenden HTTPS-Port)
- ✅ Sicher durch Login + Passwort
- ✅ Zugriffskontrolle per User-ID oder Discord-Rolle
- ✅ Cooldown verhindert Spam (Standard: 2 Minuten)

---

## 🔧 Schritt 1: FRITZ!Box einrichten

### 1.1 Benutzer für den Bot anlegen

1. Öffne: `http://fritz.box` oder `http://192.168.178.1`
2. Gehe zu: **System** → **FRITZ!Box-Benutzer**
3. Klicke auf: **Benutzer hinzufügen**
4. Konfiguriere:
   - **Benutzername:** `discordwol` (ohne Leerzeichen!)
   - **Kennwort:** Starkes Passwort (32+ Zeichen, z.B. Generator nutzen)
   - **Rechte:**
     - ✅ FRITZ!Box Einstellungen
     - ✅ Zugang auch aus dem Internet erlaubt
     - ❌ Alle anderen Häkchen WEGLASSEN
5. **Speichern**

### 1.2 Internet-Zugang prüfen

1. Gehe zu: **Internet** → **Freigaben** → **FRITZ!Box-Dienste**
2. Prüfe:
   - ✅ **Internetzugriff auf die FRITZ!Box über HTTPS aktiv**
   - Port: `41284` (sollte bereits eingestellt sein)
3. Notiere dir die **Internet-Adresse**, z.B.:
   - `https://t3y82cfb9raoyhor.myfritz.net:41284`
   - oder `https://giessencraft.ddns.net:41284`

### 1.3 Server-MAC-Adresse bestätigen

1. Gehe zu: **Heimnetz** → **Netzwerk** → **Netzwerkverbindungen**
2. Finde deinen Server
3. Notiere die MAC-Adresse (z.B. `44:8A:5B:D0:B6:4F`)

---

## 🔐 Schritt 2: Discord User/Role IDs ermitteln

### 2.1 Discord Developer Mode aktivieren

1. Discord öffnen
2. **Einstellungen** → **Erweitert**
3. ✅ **Entwicklermodus** aktivieren

### 2.2 User IDs herausfinden

1. Rechtsklick auf einen User → **ID kopieren**
2. Wiederhole für alle User, die `/bootserver` nutzen dürfen
3. Notiere die IDs (z.B. `123456789012345678`)

### 2.3 Role IDs herausfinden (optional)

1. **Servereinstellungen** → **Rollen**
2. Rechtsklick auf Rolle → **ID kopieren**
3. Notiere die IDs

**Tipp:** Nutze entweder User IDs ODER Role IDs, je nachdem was praktischer ist.

---

## ⚙️ Schritt 3: `.env` Datei konfigurieren

Erstelle/bearbeite die `.env` Datei:

```env
# Discord Bot Token (wie gehabt)
DISCORD_TOKEN="dein_token_hier"

# Discord IDs
DISCORD_GUILD_ID=1437175292232863988
DISCORD_ANNOUNCE_CHANNEL_ID=1448944338120740977

# FritzBox - WICHTIG: Komplette URL mit Port!
FRITZ_URL=https://giessencraft.ddns.net:41284
FRITZ_USER=discordwol
FRITZ_PASSWORD=dein_starkes_passwort_hier
SERVER_MAC=44:8A:5B:D0:B6:4F

# Zugriffskontrolle (mindestens EINE Option ausfüllen!)
# Option 1: Bestimmte User erlauben (komma-getrennt)
ALLOWED_USER_IDS=123456789012345678,987654321098765432

# Option 2: Bestimmte Rollen erlauben (komma-getrennt)
ALLOWED_ROLE_IDS=111222333444555666

# Cooldown in Sekunden (Standard: 120 = 2 Min)
COOLDOWN_SECONDS=120

# Rest bleibt wie vorher
LOG_LEVEL=INFO
PORT=10000
```

**WICHTIG:**
- `FRITZ_URL` muss die **komplette URL** sein: `https://....:41284`
- Mindestens `ALLOWED_USER_IDS` ODER `ALLOWED_ROLE_IDS` ausfüllen
- Wenn beide leer sind, darf JEDER den Befehl nutzen (nicht empfohlen!)

---

## 📦 Schritt 4: Dependencies installieren

```powershell
# Virtual Environment aktivieren
.venv\Scripts\Activate.ps1

# Neue Dependencies installieren
pip install -r requirements.txt
```

---

## 🧪 Schritt 5: Lokaler Test

```powershell
# Bot starten
python main.py
```

**Erwartete Ausgabe:**
```
INFO:discordbot:Bot eingeloggt als starter#8704
INFO:discordbot:1 Slash Commands für Guild 1437175292232863988 synchronisiert
```

**In Discord testen:**
1. Gib `/bootserver` ein
2. Bot sollte antworten:
   - Bei fehlender Berechtigung: "❌ Du hast keine Berechtigung..."
   - Bei Erfolg: "✅ Magic Packet gesendet! Server fährt hoch..."
3. Im Announce-Channel sollte eine Nachricht erscheinen

---

## 🌐 Schritt 6: Auf Render deployen

### 6.1 Environment Variables in Render setzen

Gehe zu deinem Render-Service → **Environment** und füge hinzu:

```
DISCORD_TOKEN = dein_token
DISCORD_GUILD_ID = 1437175292232863988
DISCORD_ANNOUNCE_CHANNEL_ID = 1448944338120740977
FRITZ_URL = https://giessencraft.ddns.net:41284
FRITZ_USER = discordwol
FRITZ_PASSWORD = dein_passwort
SERVER_MAC = 44:8A:5B:D0:B6:4F
ALLOWED_USER_IDS = 123,456,789
ALLOWED_ROLE_IDS = 111,222
COOLDOWN_SECONDS = 120
LOG_LEVEL = INFO
PORT = 10000
```

### 6.2 Deploy triggern

- Änderungen pushen nach GitHub
- Render deployed automatisch
- Bot sollte nach ~2 Min online sein

---

## 🔒 Sicherheitshinweise

### Was ist jetzt sicher?

✅ **Kein offener WOL-Port** mehr im Internet
✅ **Authentifizierung** über FRITZ!Box-Login (Benutzername + Passwort)
✅ **Zugriffskontrolle** nur bestimmte Discord-User/Rollen dürfen Command nutzen
✅ **Cooldown** verhindert Spam (Standard: 2 Min zwischen Aufrufen)
✅ **Logging** im Announce-Channel: Wer hat wann den Server gestartet?

### Was könnten Angreifer noch versuchen?

- **FRITZ!Box-Login bruteforcen:**
  - Risiko: Gering, FRITZ!Box hat eigenes Rate-Limiting
  - Schutz: Starkes Passwort (32+ Zeichen)
  
- **Discord Bot Token stehlen:**
  - Risiko: Kritisch
  - Schutz: Token nie committen, nur in Environment Variables
  
- **Berechtigte User-Accounts übernehmen:**
  - Risiko: Mittel
  - Schutz: 2FA für Discord-Accounts empfohlen

### Best Practices

1. **FRITZ!Box-Passwort:** Mindestens 32 Zeichen, Zufallsgenerator nutzen
2. **Discord Token:** Niemals in Git committen (.gitignore prüfen!)
3. **User-Whitelist:** Nur vertraute Personen hinzufügen
4. **Cooldown:** Bei Bedarf erhöhen (z.B. 300 = 5 Min)
5. **Logs prüfen:** Regelmäßig Announce-Channel checken

---

## 🐛 Fehlerbehebung

### "Login fehlgeschlagen - Benutzername oder Passwort falsch"

- **Prüfe:** Benutzername ist `discordwol` (ohne Leerzeichen!)
- **Prüfe:** Passwort korrekt kopiert (keine Leerzeichen am Anfang/Ende)
- **Teste:** Manuell im Browser unter `https://giessencraft.ddns.net:41284`
- **Prüfe:** Benutzer hat "Zugang auch aus dem Internet erlaubt"

### "Timeout - FRITZ!Box nicht erreichbar"

- **Prüfe:** `FRITZ_URL` korrekt (https:// + Port!)
- **Prüfe:** FRITZ!Box von außen erreichbar (Browser-Test)
- **Prüfe:** Firewall/Router-Probleme

### "Du hast keine Berechtigung"

- **Prüfe:** `ALLOWED_USER_IDS` oder `ALLOWED_ROLE_IDS` gesetzt
- **Prüfe:** Deine User-ID ist in der Liste
- **Debug:** In Discord: Rechtsklick auf dich → ID kopieren → mit Liste vergleichen

### "Bitte warte noch X Sekunden"

- Das ist normal! Cooldown ist aktiv.
- Warten oder `COOLDOWN_SECONDS` in `.env` reduzieren

---

## ✅ Checkliste

Vor dem Deploy auf Render:

- [ ] FRITZ!Box-Benutzer `discordwol` angelegt
- [ ] Benutzer hat "Zugang auch aus dem Internet erlaubt"
- [ ] Internet-Zugang auf Port 41284 aktiv
- [ ] User IDs oder Role IDs ermittelt
- [ ] `.env` vollständig ausgefüllt
- [ ] Lokal getestet: `python main.py`
- [ ] `/bootserver` in Discord funktioniert
- [ ] Environment Variables in Render eingetragen
- [ ] Code nach GitHub gepusht
- [ ] Render-Deploy erfolgreich

---

## 🎉 Fertig!

Dein Bot ist jetzt sicher und kann von überall genutzt werden, ohne dass du ein zusätzliches Gerät im Heimnetz brauchst!

**Von außen sichtbar:** Nur Port 41284 (FRITZ!Box-Weboberfläche)
**Keine offenen Ports:** Für WOL, TR-064 oder ähnliches
**Zugriff:** Nur über Discord, mit Login-Schutz und Berechtigungsprüfung

Bei Fragen oder Problemen: Schau in die Logs (`LOG_LEVEL=DEBUG` für mehr Details).
