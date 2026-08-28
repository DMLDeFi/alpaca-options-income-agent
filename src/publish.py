import datetime
import json

import alpaca_cli as api
from config import LOG_DIR, PROJECT_ROOT

PUBLIC_DIR = PROJECT_ROOT / "public"
STATUS_FILE = PUBLIC_DIR / "status.json"
MAX_CYCLES = 60


def _recent_cycles() -> list:
    log_file = LOG_DIR / "agent_log.jsonl"
    if not log_file.exists():
        return []
    lines = log_file.read_text().strip().splitlines()
    return [json.loads(line) for line in lines[-MAX_CYCLES:]]


def write_status() -> None:
    account = api.get_account()
    positions = api.get_positions()

    status = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "account": {
            "equity": account["equity"],
            "cash": account["cash"],
            "buying_power": account["buying_power"],
            "portfolio_value": account["portfolio_value"],
            "options_trading_level": account.get("options_trading_level"),
            "status": account["status"],
        },
        "positions": [
            {
                "symbol": p.get("symbol"),
                "qty": p.get("qty"),
                "side": p.get("side"),
                "market_value": p.get("market_value"),
                "unrealized_pl": p.get("unrealized_pl"),
                "unrealized_plpc": p.get("unrealized_plpc"),
                "avg_entry_price": p.get("avg_entry_price"),
            }
            for p in positions
        ],
        "cycles": _recent_cycles(),
    }

    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(json.dumps(status, indent=2))


if __name__ == "__main__":
    write_status()
    print(f"Wrote {STATUS_FILE}")
