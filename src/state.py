import json

from config import STATE_FILE


def load() -> dict:
    if not STATE_FILE.exists():
        return {"open_trades": []}
    return json.loads(STATE_FILE.read_text())


def save(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def record_open_trade(trade: dict) -> None:
    state = load()
    state["open_trades"].append(trade)
    save(state)


def total_open_risk() -> float:
    return sum(t["max_loss"] for t in load()["open_trades"])


def open_position_count() -> int:
    return len(load()["open_trades"])


def reconcile_with_positions(positions: list) -> None:
    """Drop tracked trades whose legs no longer show up in Alpaca's live positions (i.e. closed/expired)."""
    live_symbols = {p["symbol"] for p in positions}
    state = load()
    state["open_trades"] = [
        t for t in state["open_trades"]
        if t["short_leg"] in live_symbols or t["long_leg"] in live_symbols
    ]
    save(state)
