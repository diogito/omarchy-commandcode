#!/usr/bin/env python3
"""Print one Command Code usage record as JSON.

The panel shows three meters: the 5-hour window, the weekly window, and the
monthly subscription pool. The API returns used/cap for the first two.
Monthly has no window object; the meter is spend in the current billing
period divided by that spend plus the remaining monthly credits.

The API key is read from the environment or from local auth files and is
never written to stdout, stderr, or the record.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://api.commandcode.ai"
ENV_KEYS = ("COMMAND_CODE_API_KEY", "COMMANDCODE_API_KEY", "CMD_API_KEY")
AUTH_FILES = (
    Path.home() / ".commandcode" / "auth.json",
    Path.home() / ".pi" / "agent" / "auth.json",
    Path.home() / ".omp" / "agent" / "auth.json",
    Path.home() / ".local" / "share" / "opencode" / "auth.json",
    Path.home() / ".config" / "opencode" / "auth.json",
)
STRING_FIELDS = ("key", "apiKey", "api_key", "access", "accessToken", "token")
PLAN_NAMES = {
    "individual-ultra": "Ultra",
    "individual-pro-v1": "Pro",
    "individual-provider": "Provider",
    "individual-goat": "GOAT",
    "individual-max": "Max",
    "individual-pro": "Pro",
    "individual-go": "Go",
    "teams-pro": "Team Pro",
}
MISSING_KEY = "No Command Code API key yet. Paste one below, or run `cmd login`."
REJECTED_KEY = "Command Code rejected the API key. Paste a new one below, or run `cmd login` again."
INVALID_KEY = "Paste the API key from Command Code Studio. It is one line, with no spaces."
KEY_MIN_LENGTH = 20
KEY_MAX_LENGTH = 400


class ApiError(Exception):
    pass


def text(value: object) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return ""


def key_from_mapping(data: object) -> str:
    if not isinstance(data, dict):
        return ""
    for field in STRING_FIELDS:
        found = text(data.get(field))
        if found:
            return found
    entry = data.get("commandcode")
    found = text(entry)
    if found:
        return found
    if isinstance(entry, dict):
        return key_from_mapping(entry)
    return ""


def load_key(env: dict[str, str] | None = None, paths: tuple[Path, ...] | None = None) -> str:
    source = os.environ if env is None else env
    for name in ENV_KEYS:
        found = text(source.get(name))
        if found:
            return found
    for path in AUTH_FILES if paths is None else paths:
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        found = key_from_mapping(data)
        if found:
            return found
    return ""


def get_json(path: str, key: str) -> dict:
    request = urllib.request.Request(
        API + path,
        headers={
            "Authorization": "Bearer " + key,
            "Accept": "application/json",
            "User-Agent": "omarchy-commandcode-usage",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            raise ApiError(REJECTED_KEY) from None
        raise ApiError("Couldn't reach Command Code.") from None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        raise ApiError("Couldn't reach Command Code.") from None
    if not isinstance(payload, dict):
        raise ApiError("Couldn't read Command Code usage.")
    return payload


def number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value != value or value in (float("inf"), float("-inf")):
        return None
    return float(value)


def iso_from(value: object) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        seconds = float(value) / 1000.0 if float(value) > 10_000_000_000 else float(value)
        if seconds <= 0:
            return ""
        return datetime.fromtimestamp(seconds, timezone.utc).astimezone().isoformat()
    if isinstance(value, str) and value.strip():
        text_value = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text_value)
        except ValueError:
            return ""
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone().isoformat()
    return ""


def plan_name(plan_id: str) -> str:
    norm = plan_id.lower().replace("_", "-")
    for key, name in PLAN_NAMES.items():
        if norm.startswith(key):
            return name
    return plan_id or "Subscription"


def window_limit(raw: object, title: str) -> dict | None:
    if not isinstance(raw, dict):
        return None
    used = number(raw.get("used"))
    cap = number(raw.get("cap"))
    if used is None or cap is None or cap <= 0:
        return None
    percent = max(0.0, min(used / cap, 1.0))
    if raw.get("exceeded") is True:
        percent = 1.0
    return {
        "title": title,
        "percent": percent,
        "resetsAt": iso_from(raw.get("resetAt") or raw.get("reset_at")),
        "resetStyle": "relative",
    }


def same_instant(left: str, right: str) -> bool:
    if not left or not right:
        return False
    try:
        a = datetime.fromisoformat(left)
        b = datetime.fromisoformat(right)
    except ValueError:
        return False
    return abs((a - b).total_seconds()) < 120


def monthly_limit(credits: dict, usage: dict, period_end: str, period_start: str) -> dict | None:
    remaining = number(credits.get("monthlyCredits"))
    spent = number(usage.get("totalMonthlyCredits"))
    usage_start = iso_from(usage.get("periodStart"))
    if remaining is None or spent is None or spent < 0 or remaining < 0:
        return None
    if period_start and usage_start and not same_instant(period_start, usage_start):
        return None
    pool = remaining + spent
    if pool <= 0:
        return None
    return {
        "title": "Monthly",
        "percent": max(0.0, min(spent / pool, 1.0)),
        "resetsAt": period_end,
        "resetStyle": "date",
    }


def build(key: str) -> dict:
    credits_payload = get_json("/alpha/billing/credits", key)
    credits = credits_payload.get("credits")
    windows = credits_payload.get("windowLimits")
    if not isinstance(credits, dict) or not isinstance(windows, dict):
        raise ApiError("Couldn't read Command Code usage.")

    subscription: dict = {}
    try:
        subscription_payload = get_json("/alpha/billing/subscriptions", key)
        data = subscription_payload.get("data")
        if isinstance(data, dict):
            subscription = data
    except ApiError:
        subscription = {}

    usage: dict = {}
    try:
        usage_payload = get_json("/alpha/usage/summary", key)
        if isinstance(usage_payload, dict):
            usage = usage_payload
    except ApiError:
        usage = {}

    plan_id = subscription.get("planId") if isinstance(subscription.get("planId"), str) else ""
    period_end = iso_from(subscription.get("currentPeriodEnd"))
    period_start = iso_from(subscription.get("currentPeriodStart"))
    limits = []
    five_hour = window_limit(windows.get("fiveHour") or windows.get("five_hour"), "5-hour")
    weekly = window_limit(windows.get("weekly"), "Weekly")
    monthly = monthly_limit(credits, usage, period_end, period_start)
    for entry in (five_hour, weekly, monthly):
        if entry:
            limits.append(entry)
    if not limits:
        raise ApiError("Couldn't read Command Code usage.")

    return {
        "ok": True,
        "planName": plan_name(plan_id),
        "updatedAt": datetime.now().astimezone().isoformat(),
        "limits": limits,
    }


def env_key_name(env: dict[str, str] | None = None) -> str:
    source = os.environ if env is None else env
    for name in ENV_KEYS:
        if text(source.get(name)):
            return name
    return ""


def valid_key(value: str) -> bool:
    if not KEY_MIN_LENGTH <= len(value) <= KEY_MAX_LENGTH:
        return False
    if any(character.isspace() for character in value):
        return False
    return True


def store_key(key: str, path: Path | None = None) -> None:
    """Save a key where `cmd login` keeps it. The key is not logged."""
    cleaned = key.strip()
    if not valid_key(cleaned):
        raise ApiError(INVALID_KEY)
    target = path or (Path.home() / ".commandcode" / "auth.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(target.parent, 0o700)
    payload: dict = {}
    if target.exists():
        try:
            current = json.loads(target.read_text())
        except (OSError, json.JSONDecodeError):
            raise ApiError("Couldn't update ~/.commandcode/auth.json. It is not a JSON object.") from None
        if not isinstance(current, dict):
            raise ApiError("Couldn't update ~/.commandcode/auth.json. It is not a JSON object.")
        payload = current
    updated = False
    for field in STRING_FIELDS:
        if isinstance(payload.get(field), str):
            payload[field] = cleaned
            updated = True
    if not updated:
        payload["apiKey"] = cleaned
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n")
    os.chmod(temporary, 0o600)
    os.replace(temporary, target)
    os.chmod(target, 0o600)


def failure(message: str, needs_key: bool = False) -> dict:
    report = {"ok": False, "error": message}
    if needs_key:
        report["needsKey"] = True
    return report


def store_from_stdin(stream=None, env: dict[str, str] | None = None, path: Path | None = None) -> dict:
    name = env_key_name(env)
    if name:
        return failure(
            f"{name} is set for the Omarchy shell and overrides a saved key. "
            "Update that variable, or unset it and paste the key again.",
            needs_key=True,
        )
    raw = (sys.stdin if stream is None else stream).readline()
    try:
        cleaned = raw.strip()
        store_key(cleaned, path)
        if path is not None:
            return {"ok": True, "stored": True}
        return build(cleaned)
    except ApiError as error:
        message = str(error)
        needs_key = message in (INVALID_KEY, REJECTED_KEY) or message.startswith("Couldn't update")
        return failure(message, needs_key=needs_key)


def emit(report: dict) -> None:
    json.dump(report, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")


def main() -> int:
    if "--store-key" in sys.argv[1:]:
        emit(store_from_stdin())
        return 0
    key = load_key()
    if not key:
        report = failure(MISSING_KEY, needs_key=True)
    else:
        try:
            report = build(key)
        except ApiError as error:
            needs_key = str(error) == REJECTED_KEY
            report = failure(str(error), needs_key=needs_key)
    emit(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
