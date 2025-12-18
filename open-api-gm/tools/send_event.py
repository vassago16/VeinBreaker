import json
import sys
from urllib import request

API = "http://localhost:8000/emit"

EVENT_TYPES = [
    "signal",
    "log",
    "combat_log",
    "combat_state",
    "interrupt",
    "character_update",
    "declare_chain",
    "chain_rejected",
]


def prompt(msg, default=None):
    val = input(f"{msg} " + (f"[{default}] " if default else "")) or default
    return val


def build_payload(ev_type):
    payload = {"type": ev_type}
    if ev_type == "signal":
        payload["signalType"] = prompt("Signal type", "system")
        payload["text"] = prompt("Text", "Test signal")
    elif ev_type in ("log", "combat_log"):
        payload["logType"] = prompt("Log type", "system")
        payload["text"] = prompt("Text", "Test log line")
    elif ev_type == "combat_state":
        payload["active"] = prompt("Active? (y/n)", "y").lower().startswith("y")
    elif ev_type == "interrupt":
        payload["text"] = prompt("Text", "Interrupt fired")
    elif ev_type == "character_update":
        payload["character"] = {
            "hp": {"current": 10, "max": 12},
            "rp": 3,
            "veinscore": 1,
            "attributes": {"str": 12, "dex": 12, "int": 12, "wil": 12},
        }
    elif ev_type == "declare_chain":
        payload["maxLength"] = 3
        payload["chainRules"] = {"min": 0, "max": 3, "source": "Test"}
        payload["abilities"] = [
            {"id": "ab.test.attack", "name": "Test Attack", "type": "attack", "cost": 1, "cooldown": 0, "effect": "Test effect"},
            {"id": "ab.test.move", "name": "Test Move", "type": "movement", "cost": 0, "cooldown": 0, "effect": "Step lightly"},
        ]
    elif ev_type == "chain_rejected":
        payload["reason"] = prompt("Reason", "Invalid chain")
    else:
        payload["text"] = prompt("Text", f"Test {ev_type}")
    return payload


def main():
    session_id = prompt("Session ID", "test-session")
    print("Choose event type:")
    for idx, t in enumerate(EVENT_TYPES, 1):
        print(f"{idx}. {t}")
    try:
        choice = int(prompt("Number", "1")) - 1
        ev_type = EVENT_TYPES[choice]
    except Exception:
        print("Invalid selection")
        sys.exit(1)

    payload = build_payload(ev_type)
    body = json.dumps({"session_id": session_id, **payload}).encode("utf-8")
    req = request.Request(API, data=body, headers={"Content-Type": "application/json"})
    try:
        with request.urlopen(req) as resp:
            data = resp.read().decode("utf-8")
            print("Response:", data)
    except Exception as e:
        print("Error sending event:", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
