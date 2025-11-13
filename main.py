import asyncio
import hashlib
import hmac
import json
import logging
import os
import random
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import httpx
import discord
from discord.ext import commands
from dotenv import load_dotenv
from flask import Flask


load_dotenv()


DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
TUYA_CLIENT_ID = os.getenv("TUYA_CLIENT_ID")
TUYA_CLIENT_SECRET = os.getenv("TUYA_CLIENT_SECRET")
TUYA_DEVICE_ID = os.getenv("TUYA_DEVICE_ID")
DISCORD_ANNOUNCE_CHANNEL_ID = int(os.getenv("DISCORD_ANNOUNCE_CHANNEL_ID", "0"))
TUYA_REGION = (os.getenv("TUYA_REGION") or "https://openapi.tuyaeu.com").rstrip("/")
API_BASE = TUYA_REGION

if not DISCORD_TOKEN:
	raise RuntimeError("DISCORD_TOKEN must be set in the environment or .env file.")
if not TUYA_CLIENT_ID or not TUYA_CLIENT_SECRET or not TUYA_DEVICE_ID:
	raise RuntimeError("Tuya credentials (TUYA_CLIENT_ID, TUYA_CLIENT_SECRET, TUYA_DEVICE_ID) must be configured.")


LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
logger = logging.getLogger("discordbot")


SHUTDOWN_TRIGGER_SUBSTRING = "Speichern & Herunterfahren wird eingeleitet."
SHUTDOWN_CANCEL_TEXT = "Server läuft, und ist Online."
SHUTDOWN_TIMEOUT_SECONDS = 3 * 60
METADATA_CACHE_SECONDS = 15 * 60
TOKEN_SAFETY_MARGIN_MS = 10_000


# Render requires a web process listening on a port, so keep a tiny Flask app alive.
app = Flask(__name__)


@app.get("/")
def home() -> tuple[str, int]:
	return "✅ Discord Tuya Bot is running!", 200


def run_web() -> None:
	port = int(os.getenv("PORT", "10000"))
	app.run(host="0.0.0.0", port=port)


threading.Thread(target=run_web, name="FlaskThread", daemon=True).start()


def _normalize_switch_value(value: Any) -> Any:
	if isinstance(value, bool):
		return value
	if isinstance(value, (int, float)):
		return value
	if isinstance(value, str):
		lowered = value.strip().lower()
		if lowered in {"true", "false"}:
			return lowered == "true"
		return lowered
	return value


@dataclass
class SwitchInfo:
	code: str
	on_value: Any
	off_value: Any

	def is_on_value(self, raw_value: Any) -> bool:
		normalized_raw = _normalize_switch_value(raw_value)
		normalized_on = _normalize_switch_value(self.on_value)
		if normalized_raw == normalized_on:
			return True
		try:
			return str(normalized_raw).lower() == str(normalized_on).lower()
		except Exception:
			return False

	def is_off_value(self, raw_value: Any) -> bool:
		normalized_raw = _normalize_switch_value(raw_value)
		normalized_off = _normalize_switch_value(self.off_value)
		if normalized_raw == normalized_off:
			return True
		try:
			return str(normalized_raw).lower() == str(normalized_off).lower()
		except Exception:
			return False


@dataclass
class DeviceMetadata:
	switch: SwitchInfo
	functions: List[Dict[str, Any]]
	fetched_at: float


@dataclass
class StatusEntry:
	code: str
	value: Any
	scale: Optional[int] = None
	unit: Optional[str] = None
	raw: Optional[Dict[str, Any]] = None
	updated_at: Optional[float] = None


@dataclass
class ShutdownWatcher:
	channel_id: int
	message_id: int
	trigger_author_id: Optional[int]
	cancel_event: asyncio.Event
	started_at: float
	task: Optional[asyncio.Task] = None


_http_client: Optional[httpx.AsyncClient] = None
_token: Optional[str] = None
_token_expire_ms: int = 0
_token_lock = asyncio.Lock()
_metadata_cache: Optional[DeviceMetadata] = None
_metadata_lock = asyncio.Lock()
_shutdown_lock = asyncio.Lock()
_shutdown_watcher: Optional[ShutdownWatcher] = None


def now_ms() -> int:
	return int(time.time() * 1000)


def sha256_hex(payload: bytes) -> str:
	return hashlib.sha256(payload).hexdigest()


def hmac_sha256_upper(secret: str, message: str) -> str:
	mac = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256)
	return mac.hexdigest().upper()


EMPTY_BODY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


async def get_http_client() -> httpx.AsyncClient:
	global _http_client
	if _http_client is None:
		_http_client = httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=15.0))
	return _http_client


async def get_access_token(client: httpx.AsyncClient) -> str:
	global _token, _token_expire_ms
	async with _token_lock:
		if _token and now_ms() < _token_expire_ms - TOKEN_SAFETY_MARGIN_MS:
			return _token

		t = str(now_ms())
		nonce = uuid.uuid4().hex
		method = "GET"
		path = "/v1.0/token?grant_type=1"
		headers_string = ""
		string_to_sign = f"{method}\n{EMPTY_BODY_SHA256}\n{headers_string}\n{path}"
		sign_base = f"{TUYA_CLIENT_ID}{t}{nonce}{string_to_sign}"
		signature = hmac_sha256_upper(TUYA_CLIENT_SECRET, sign_base)

		headers = {
			"client_id": TUYA_CLIENT_ID,
			"sign": signature,
			"t": t,
			"sign_method": "HMAC-SHA256",
			"nonce": nonce,
			"Content-Type": "application/json",
			"Accept": "application/json",
		}

		url = API_BASE + path
		response = await client.get(url, headers=headers)
		response.raise_for_status()
		payload = response.json()
		result = payload.get("result") or {}
		token = result.get("access_token")
		expire_seconds = int(result.get("expire_time", 7200))
		if not token:
			raise RuntimeError(f"Tuya token response did not contain access_token: {payload}")
		_token = token
		_token_expire_ms = now_ms() + expire_seconds * 1000
		return token


async def tuya_service_request(
	client: httpx.AsyncClient,
	method: str,
	path: str,
	access_token: str,
	body: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
	method_upper = method.upper()
	nonce = uuid.uuid4().hex
	t = str(now_ms())
	if body is None:
		body_bytes = b""
		content_sha = EMPTY_BODY_SHA256
	else:
		body_bytes = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
		content_sha = sha256_hex(body_bytes)

	headers_string = f"client_id:{TUYA_CLIENT_ID}\naccess_token:{access_token}\n"
	string_to_sign = f"{method_upper}\n{content_sha}\n{headers_string}\n{path}"
	sign_base = f"{TUYA_CLIENT_ID}{access_token}{t}{nonce}{string_to_sign}"
	signature = hmac_sha256_upper(TUYA_CLIENT_SECRET, sign_base)

	headers = {
		"client_id": TUYA_CLIENT_ID,
		"sign": signature,
		"t": t,
		"sign_method": "HMAC-SHA256",
		"nonce": nonce,
		"access_token": access_token,
		"Signature-Headers": "client_id:access_token",
		"Content-Type": "application/json",
		"Accept": "application/json",
	}

	url = API_BASE + path
	if method_upper == "GET":
		response = await client.get(url, headers=headers)
	elif method_upper == "POST":
		response = await client.post(url, headers=headers, content=body_bytes)
	else:
		raise ValueError(f"Unsupported Tuya HTTP method: {method}")
	response.raise_for_status()
	return response.json()


async def get_device_functions(client: httpx.AsyncClient, access_token: str, device_id: str) -> List[Dict[str, Any]]:
	payload = await tuya_service_request(
		client,
		"GET",
		f"/v1.0/iot-03/devices/{device_id}/functions",
		access_token,
	)
	result = payload.get("result") or {}
	functions: Optional[List[Dict[str, Any]]]
	if isinstance(result, dict):
		functions = result.get("functions")
	elif isinstance(result, list) and result:
		functions = result[0].get("functions")
	else:
		functions = None
	return functions or []


def choose_switch_dp(functions: List[Dict[str, Any]]) -> Tuple[str, Any, Any]:
	preferred_codes = [
		"switch_1",
		"switch",
		"switch_led",
		"master",
		"master_switch",
		"power",
		"relay_status",
	]
	by_code = {str(func.get("code")): func for func in functions if func.get("code")}
	chosen: Optional[Dict[str, Any]] = None
	for code in preferred_codes:
		if code in by_code:
			chosen = by_code[code]
			break
	if not chosen:
		for func in functions:
			func_type = str(func.get("type", "")).lower()
			code = str(func.get("code", "")).lower()
			if func_type in {"boolean", "enum"} and ("switch" in code or code in {"power", "relay_status", "power_switch"}):
				chosen = func
				break
	if not chosen:
		for func in functions:
			if str(func.get("type", "")).lower() == "boolean":
				chosen = func
				break
	if not chosen:
		raise RuntimeError("No suitable Tuya switch datapoint could be determined.")

	func_type = str(chosen.get("type", "")).lower()
	code = chosen.get("code")
	if not isinstance(code, str) or not code:
		raise RuntimeError("Chosen switch datapoint does not expose a valid code.")

	if func_type == "boolean":
		return code, True, False

	if func_type == "enum":
		raw_values = chosen.get("values") or "{}"
		try:
			parsed = json.loads(raw_values)
		except Exception:
			parsed = {}
		range_values = [str(v).lower() for v in parsed.get("range", [])]
		on_aliases = ["on", "open", "1", "true"]
		off_aliases = ["off", "close", "0", "false"]
		on_value = next((val for val in range_values if val in on_aliases), None)
		off_value = next((val for val in range_values if val in off_aliases), None)
		if on_value is None and range_values:
			on_value = range_values[0]
		if off_value is None and len(range_values) > 1:
			off_value = range_values[1]
		if on_value is None or off_value is None:
			raise RuntimeError(f"Unable to map enum values for switch datapoint {code}.")
		return code, on_value, off_value

	raise RuntimeError(f"Unsupported switch datapoint type for {code}: {func_type}")


async def get_device_metadata(
	client: httpx.AsyncClient,
	access_token: str,
	force_refresh: bool = False,
) -> DeviceMetadata:
	cached: Optional[DeviceMetadata]
	if not force_refresh:
		async with _metadata_lock:
			cached = _metadata_cache
		if cached and time.time() - cached.fetched_at < METADATA_CACHE_SECONDS:
			return cached

	functions = await get_device_functions(client, access_token, TUYA_DEVICE_ID)
	code, on_value, off_value = choose_switch_dp(functions)
	metadata = DeviceMetadata(
		switch=SwitchInfo(code=code, on_value=on_value, off_value=off_value),
		functions=functions,
		fetched_at=time.time(),
	)
	async with _metadata_lock:
		_metadata_cache = metadata
	return metadata


async def send_switch_command(
	client: httpx.AsyncClient,
	access_token: str,
	device_id: str,
	switch_info: SwitchInfo,
	turn_on: bool,
) -> Dict[str, Any]:
	value = switch_info.on_value if turn_on else switch_info.off_value
	body = {"commands": [{"code": switch_info.code, "value": value}]}
	return await tuya_service_request(client, "POST", f"/v1.0/iot-03/devices/{device_id}/commands", access_token, body)


async def get_device_status(client: httpx.AsyncClient, access_token: str, device_id: str) -> Dict[str, Any]:
	return await tuya_service_request(client, "GET", f"/v1.0/iot-03/devices/{device_id}/status", access_token)


def _to_int(value: Any) -> Optional[int]:
	if value is None:
		return None
	if isinstance(value, int):
		return value
	if isinstance(value, float) and value.is_integer():
		return int(value)
	if isinstance(value, str):
		try:
			return int(value)
		except ValueError:
			return None
	return None


def _coerce_timestamp(value: Any) -> Optional[float]:
	if value is None:
		return None
	if isinstance(value, (int, float)):
		ts = float(value)
	elif isinstance(value, str):
		text = value.strip()
		if not text:
			return None
		try:
			ts = float(text)
		except ValueError:
			return None
	else:
		return None
	if ts <= 0:
		return None
	if ts > 1_000_000_000_000:
		return ts / 1000.0
	if ts > 1_000_000_000:
		return ts
	return None


def _extract_updated_at(raw: Dict[str, Any]) -> Optional[float]:
	for key in ("t", "time", "update_time", "updateTime", "bizTime"):
		if key in raw:
			ts = _coerce_timestamp(raw.get(key))
			if ts is not None:
				return ts
	return None


def parse_status_result(raw_status: Any) -> Dict[str, StatusEntry]:
	status_map: Dict[str, StatusEntry] = {}
	if isinstance(raw_status, list):
		for item in raw_status:
			if not isinstance(item, dict):
				continue
			code = item.get("code")
			if not isinstance(code, str) or not code:
				continue
			value = item.get("value")
			scale = _to_int(item.get("scale"))
			unit = item.get("unit") if isinstance(item.get("unit"), str) else None
			updated_at = _extract_updated_at(item)
			status_map[code] = StatusEntry(
				code=code,
				value=value,
				scale=scale,
				unit=unit,
				raw=item,
				updated_at=updated_at,
			)
	elif isinstance(raw_status, dict):
		for code, value in raw_status.items():
			if isinstance(code, str) and code:
				status_map[code] = StatusEntry(code=code, value=value)
	return status_map


async def fetch_switch_status(force_metadata_refresh: bool = False) -> Tuple[bool, DeviceMetadata, Dict[str, StatusEntry]]:
	client = await get_http_client()
	access_token = await get_access_token(client)
	metadata = await get_device_metadata(client, access_token, force_refresh=force_metadata_refresh)
	status_payload = await get_device_status(client, access_token, TUYA_DEVICE_ID)
	if not status_payload.get("success", True):
		raise RuntimeError(f"Tuya status request failed: {status_payload}")
	status_map = parse_status_result(status_payload.get("result"))
	switch_entry = status_map.get(metadata.switch.code)
	if switch_entry is None and not force_metadata_refresh:
		return await fetch_switch_status(force_metadata_refresh=True)
	raw_value = switch_entry.value if switch_entry else None
	is_on = switch_entry is not None and metadata.switch.is_on_value(raw_value)
	return is_on, metadata, status_map


async def set_plug_state(turn_on: bool, metadata: Optional[DeviceMetadata] = None) -> Tuple[bool, Optional[str]]:
	client = await get_http_client()
	access_token = await get_access_token(client)
	if metadata is None:
		metadata = await get_device_metadata(client, access_token)
	response = await send_switch_command(client, access_token, TUYA_DEVICE_ID, metadata.switch, turn_on)
	if response.get("success"):
		return True, None
	return False, json.dumps(response, ensure_ascii=False)


def _next_from_pool(pool: deque[str], source: List[str]) -> str:
	if not source:
		return ""
	if not pool:
		shuffled = source[:]
		random.shuffle(shuffled)
		pool.extend(shuffled)
	return pool.popleft()


SUCCESS_MESSAGES = [
	"✅ Alles klar, ich hab den Stecker umgelegt — könnte 'ne Weile dauern, hol dir ruhig 'nen Snack.",
	"⚡ Power ist dran. Server startet jetzt; das kann etwas länger dauern, vielleicht Popcorn holen? 🍿",
	"🖥️ Server wird hochgefahren. Sitzt das Hemd locker? Das dauert noch ein bisschen.",
	"🚀 Startsequenz läuft — dauert eine ganze Weile. Lehn dich zurück und chille kurz.",
	"🎮 Maschine bekommt Saft. Gib ihm Zeit, das kann einige Minuten dauern. Kaffee empfohlen ☕",
	"🔌 Strom ist drauf, die Systeme booten. Kann etwas dauern — entspann dich solange.",
	"📡 Signal gesendet. Server braucht einen Moment, bleib kurz geduldig.",
	"🤖 Server wird geweckt. Das dauert leider ein Weilchen — schnapp dir 'nen Snack und entspann dich.",
	"🔥 Es geht los — aber das Hochfahren zieht sich. Mach's dir gemütlich.",
	"🟢 Relais geschaltet. Boot-Vorgang kann länger dauern, lehn dich zurück und chill.",
	"🐉 Rufe den Server-Drachen — dauert eine Weile, also ruhig bleiben und Snacks verteilen.",
	"🧠 Rechenhirn wird initialisiert. Bitte etwas Geduld, das kann länger dauern.",
	"🌩️ Energie unterwegs, Dienste kommen hoch. Könnte etwas Zeit brauchen — kurz durchatmen.",
	"🛰️ Launch bestätigt. Warte kurz — das Hochfahren nimmt seine Zeit.",
	"🛠️ Power an. Systeme benötigen Zeit zum Hochfahren, nimm dir 'ne Pause.",
	"🎯 Auftrag ausgeführt — Server startet, das kann 'ne Weile dauern. Perfekter Moment für einen Kaffee.",
	"🌐 Netzwerk und Dienste werden gejagt — bitte etwas Geduld, das kann dauern.",
	"🕹️ Arcade startet bald, aber das Hochfahren ist kein Sprint. Hol dir 'nen Snack.",
	"💾 Laufwerke werden geweckt. Das kann dauern — perfekt für ein kurzes Stretching.",
	"🪄 Abrakadabra… Server startet gleich, dauert aber noch. Entspann dich und genieße den Moment.",
	"🔋 Stromadern online. Server respawnt gleich — gönn dir kurz AFK.",
	"🎧 Bootbeat läuft. Gib der Maschine ein paar Takte zum Aufwachen.",
	"🚁 Rotoren drehen, Server hebt ab. Lehnen wir uns zurück und genießen den Tower-View.",
	"🛎️ Klingel gedrückt, Butler-Server macht sich fertig. Noch kurz Geduld bitte.",
	"🛸 Uplink geöffnet, Systeme booten. Chill kurz, warp dauert einen Moment.",
]


FAIL_MESSAGES = [
	"❌ Hm, das hat nicht geklappt: {error}",
	"⚠️ Konnte Power nicht schalten: {error}",
	"🛑 Fehler beim Einschalten: {error}",
	"😵 Unerwarteter Tuya-Fehler: {error}",
	"🐛 Glitch im System: {error}",
	"🧱 Der Plug hat nicht reagiert: {error}",
	"🚫 Aktion abgelehnt: {error}",
	"🪫 Keine erfolgreiche Bestätigung: {error}",
	"📵 Schalter verweigert den Dienst: {error}",
	"🔻 Powerflip daneben gegangen: {error}",
	"🪧 Tuya meinte nein: {error}",
]


POWERDOWN_MESSAGES = [
	"😴 Rechner schlummert seit {minutes:.1f} Minuten unter {power:.1f} W. Ich ziehe mal den Stecker. Gute Nacht! 🌙",
	"🔌 Stromsparmodus deluxe: {minutes:.1f} Minuten nur {power:.1f} W. Stecker geht jetzt schlafen.",
	"🛏️ Unter {power:.1f} W seit {minutes:.1f} Minuten? Klingt nach Schlafenszeit. Klick – aus.",
	"👋 Der PC tut seit {minutes:.1f} Minuten so, als wär nix los ({power:.1f} W). Ich mach ihm das Licht aus.",
	"🌌 Idle-Level bei {power:.1f} W über {minutes:.1f} Minuten. Ich beende die Sitzung wie ein Boss.",
	"🧘‍♂️ Chillige {power:.1f} W seit {minutes:.1f} Minuten. Ich rolle das Stromkabel ein.",
	"🕯️ Drei Minuten Ruhe, {power:.1f} W Restglühen – Stecker zieht aus.",
	"🌙 Countdown abgelaufen. {minutes:.1f} Minuten Funkstille bei {power:.1f} W – Licht aus.",
]


ALREADY_ON_MESSAGES = [
	"😑 Chill mal – der Stecker feuert schon.",
	"🤨 Interessant… du willst einschalten, was längst glänzt. Vielleicht erst Kaffee, dann Commands?",
	"🌀 Der Strom fließt bereits. Wenn du Langeweile hast, streichel doch den Server statt mich zu spammen.",
	"🗯️ `/bootserver` nochmal? Mutig. Aber nö – der Plug ist an, und ich bin kein Lichtschalter auf Speed.",
	"🧯 Alarm abbrechen! Wir brennen schon. Bitte nicht noch mehr `/bootserver`-Feuerwerk.",
	"🎉 Überraschung: Alles läuft bereits. Such dir 'nen anderen Knopf zum Drücken.",
	"🟩 Schon grün. Vielleicht lieber `/status` im Kopf ausführen?",
	"🧠 Brain check: Strom war nie weg. Versuch's mal mit einem Victory Dance statt `/bootserver`.",
]


SHUTDOWN_START_MESSAGES = [
	"⌛ Shutdown-Countdown läuft. Warte auf das grüne Licht.",
	"📉 Speichere alles, wir zählen jetzt rückwärts.",
	"🕒 Drei Minuten Timer aktiv. Sag mir Bescheid, falls alles safe ist.",
	"🚨 Countdown scharfgestellt. Bis zum All-Clear bleib ich wachsam.",
	"🛰️ Shutdown-Sequenz eingeleitet. Warte auf 'Server läuft, und ist Online.'",
]


SHUTDOWN_CANCEL_MESSAGES = [
	"🟢 Entwarnung erhalten. Countdown gestoppt, Stecker bleibt drin.",
	"✅ Alles klar, Shutdown abgebrochen. Server bleibt wach.",
	"🎈 Abbruch bestätigt – keine Steckertanz-Aktion nötig.",
	"💾 All clear! Countdown gelöscht, weiter geht's.",
]


SHUTDOWN_TIMEOUT_MESSAGES = [
	"😴 Keine Rückmeldung seit {minutes:.1f} Minuten. Stecker ist jetzt aus.",
	"🔴 Countdown durchgelaufen – nach {minutes:.1f} Minuten Ruhe den Plug getrennt.",
	"🌘 Drei Minuten ohne Lebenszeichen. Strom weg, gute Nacht.",
	"🪫 Keiner hat 'Server läuft, und ist Online.' gesagt – der Plug ruht jetzt.",
]


ALREADY_OFF_MESSAGES = [
	"🔌 Countdown vorbei, aber der Stecker war schon längst draußen.",
	"🪵 Timer fertig, doch der Plug chillte bereits offline.",
	"📻 Funkstille bestätigt – der Strom war schon weg.",
]


_success_pool: deque[str] = deque()
_fail_pool: deque[str] = deque()
_powerdown_pool: deque[str] = deque()
_already_on_pool: deque[str] = deque()
_shutdown_start_pool: deque[str] = deque()
_shutdown_cancel_pool: deque[str] = deque()
_shutdown_timeout_pool: deque[str] = deque()
_already_off_pool: deque[str] = deque()


def get_next_success() -> str:
	return _next_from_pool(_success_pool, SUCCESS_MESSAGES)


def get_next_failure() -> str:
	return _next_from_pool(_fail_pool, FAIL_MESSAGES)


def get_next_powerdown() -> str:
	return _next_from_pool(_powerdown_pool, POWERDOWN_MESSAGES)


def get_next_already_on() -> str:
	return _next_from_pool(_already_on_pool, ALREADY_ON_MESSAGES)


def get_next_shutdown_start() -> str:
	return _next_from_pool(_shutdown_start_pool, SHUTDOWN_START_MESSAGES)


def get_next_shutdown_cancel() -> str:
	return _next_from_pool(_shutdown_cancel_pool, SHUTDOWN_CANCEL_MESSAGES)


def get_next_shutdown_timeout() -> str:
	return _next_from_pool(_shutdown_timeout_pool, SHUTDOWN_TIMEOUT_MESSAGES)


def get_next_already_off() -> str:
	return _next_from_pool(_already_off_pool, ALREADY_OFF_MESSAGES)


async def send_channel_message(channel_id: int, content: str) -> bool:
	channel = bot.get_channel(channel_id)
	if channel is None:
		try:
			channel = await bot.fetch_channel(channel_id)
		except Exception as exc:
			logger.warning("Unable to load channel %s: %s", channel_id, exc)
			return False
	try:
		await channel.send(content)
		return True
	except Exception as exc:
		logger.warning("Failed to send message to channel %s: %s", channel_id, exc)
		return False


async def start_shutdown_watch(trigger_message: discord.Message) -> None:
	is_on, metadata, _ = await fetch_switch_status()
	if not is_on:
		logger.info("Shutdown trigger ignored because the plug is already off.")
		return

	async with _shutdown_lock:
		existing = _shutdown_watcher
		if existing is not None:
			existing.cancel_event.set()
		cancel_event = asyncio.Event()
		watcher = ShutdownWatcher(
			channel_id=trigger_message.channel.id,
			message_id=trigger_message.id,
			trigger_author_id=getattr(trigger_message.author, "id", None),
			cancel_event=cancel_event,
			started_at=time.time(),
		)
		_shutdown_watcher = watcher

	watcher.task = asyncio.create_task(_shutdown_countdown(watcher, metadata))
	logger.info(
		"Shutdown countdown started (message=%s, channel=%s)",
		trigger_message.id,
		trigger_message.channel.id,
	)


async def cancel_shutdown_watch(cancel_message: discord.Message) -> bool:
	async with _shutdown_lock:
		watcher = _shutdown_watcher
		if watcher is None or watcher.channel_id != cancel_message.channel.id:
			return False
		_shutdown_watcher = None
	watcher.cancel_event.set()
	await send_channel_message(watcher.channel_id, get_next_shutdown_cancel())
	if watcher.task is not None:
		try:
			await watcher.task
		except Exception as exc:
			logger.warning("Shutdown countdown task raised during cancellation: %s", exc)
	logger.info("Shutdown countdown cancelled (message=%s)", cancel_message.id)
	return True


async def _finalize_shutdown_state(target: ShutdownWatcher) -> None:
	async with _shutdown_lock:
		if _shutdown_watcher is target:
			_shutdown_watcher = None


async def _shutdown_countdown(watcher: ShutdownWatcher, metadata: DeviceMetadata) -> None:
	minutes = SHUTDOWN_TIMEOUT_SECONDS / 60.0
	await send_channel_message(watcher.channel_id, get_next_shutdown_start())
	try:
		await asyncio.wait_for(watcher.cancel_event.wait(), timeout=SHUTDOWN_TIMEOUT_SECONDS)
		logger.info("Shutdown countdown ended early via cancellation (channel=%s)", watcher.channel_id)
	except asyncio.TimeoutError:
		logger.info("Shutdown countdown elapsed; attempting to power off (channel=%s)", watcher.channel_id)
		try:
			is_on, current_metadata, _ = await fetch_switch_status()
		except Exception as exc:
			logger.exception("Failed to refresh switch status before shutdown: %s", exc)
			await send_channel_message(
				watcher.channel_id,
				get_next_failure().format(error=str(exc)),
			)
			await _finalize_shutdown_state(watcher)
			return

		if not is_on:
			await send_channel_message(watcher.channel_id, get_next_already_off())
			await _finalize_shutdown_state(watcher)
			return

		try:
			success, error = await set_plug_state(False, metadata=current_metadata)
		except Exception as exc:
			logger.exception("Failed to turn off plug after countdown: %s", exc)
			await send_channel_message(
				watcher.channel_id,
				get_next_failure().format(error=str(exc)),
			)
			await _finalize_shutdown_state(watcher)
			return

		if success:
			await send_channel_message(
				watcher.channel_id,
				get_next_shutdown_timeout().format(minutes=minutes, power=0.0),
			)
		else:
			await send_channel_message(
				watcher.channel_id,
				get_next_failure().format(error=error or "Tuya error"),
			)
	finally:
		await _finalize_shutdown_state(watcher)


intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)
bot.tree_synced = False


@bot.event
async def on_ready() -> None:
	if not bot.tree_synced:
		try:
			await bot.tree.sync()
			bot.tree_synced = True
			logger.info("Slash commands synced successfully.")
		except Exception as exc:
			logger.error("Failed to sync slash commands: %s", exc)
	logger.info("Logged in as %s (id=%s)", bot.user, bot.user.id if bot.user else "?")


@bot.event
async def on_message(message: discord.Message) -> None:
	if message.author == bot.user:
		content = message.content or ""
		lowered = content.lower()
		if SHUTDOWN_TRIGGER_SUBSTRING.lower() in lowered:
			try:
				await start_shutdown_watch(message)
			except Exception as exc:
				logger.exception("Failed to start shutdown countdown: %s", exc)
		elif content.strip() == SHUTDOWN_CANCEL_TEXT:
			try:
				cancelled = await cancel_shutdown_watch(message)
				if not cancelled and DISCORD_ANNOUNCE_CHANNEL_ID > 0:
					await send_channel_message(
						DISCORD_ANNOUNCE_CHANNEL_ID,
						"ℹ️ Shutdown-Abbruch erkannt, aber kein Countdown war aktiv.",
					)
			except Exception as exc:
				logger.exception("Failed to cancel shutdown countdown: %s", exc)
	await bot.process_commands(message)


async def ensure_shutdown_cleared_on_turnoff() -> None:
	async with _shutdown_lock:
		watcher = _shutdown_watcher
		if watcher is None:
			return
		_shutdown_watcher = None
	watcher.cancel_event.set()
	if watcher.task is not None:
		try:
			await watcher.task
		except Exception:
			pass


@bot.tree.command(name="bootserver", description="Turn on the smart plug (boot the server).")
async def bootserver(interaction: discord.Interaction) -> None:
	await interaction.response.defer(thinking=True)
	try:
		is_on, metadata, _ = await fetch_switch_status()
		if is_on:
			await interaction.followup.send(get_next_already_on())
			return

		success, error = await set_plug_state(True, metadata=metadata)
		if success:
			await ensure_shutdown_cleared_on_turnoff()
			await interaction.followup.send(get_next_success())
		else:
			await interaction.followup.send(get_next_failure().format(error=error or "Tuya error"))
	except httpx.HTTPStatusError as exc:
		body = exc.response.text if exc.response else str(exc)
		await interaction.followup.send(
			get_next_failure().format(error=f"HTTP {exc.response.status_code if exc.response else '???'} - {body}"),
		)
	except Exception as exc:
		logger.exception("Unexpected error during /bootserver: %s", exc)
		await interaction.followup.send(get_next_failure().format(error=str(exc)))


@bot.command(name="ping")
async def ping(ctx: commands.Context) -> None:
	await ctx.send("🏓 Pong!")


if __name__ == "__main__":
	bot.run(DISCORD_TOKEN)
