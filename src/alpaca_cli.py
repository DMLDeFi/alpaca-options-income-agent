import json
import subprocess

from config import ALPACA_API_KEY, ALPACA_BIN, ALPACA_SECRET_KEY

_ENV = {"ALPACA_API_KEY": ALPACA_API_KEY, "ALPACA_SECRET_KEY": ALPACA_SECRET_KEY}


def _run(args: list[str]):
    import os

    env = {**os.environ, **_ENV}
    result = subprocess.run(
        [ALPACA_BIN, *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"alpaca {' '.join(args)} failed: {result.stderr.strip()}")
    return json.loads(result.stdout) if result.stdout.strip() else None


def get_account() -> dict:
    return _run(["account", "get"])


def get_positions() -> list:
    return _run(["position", "list"]) or []


def get_clock() -> dict:
    return _run(["clock"])


def get_latest_stock_price(symbol: str) -> float:
    resp = _run(["data", "latest-quote", "--symbol", symbol])
    quote = resp["quote"]
    return (quote["ap"] + quote["bp"]) / 2


def get_daily_bars(symbol: str, limit: int = 30) -> list:
    import datetime

    start = (datetime.date.today() - datetime.timedelta(days=int(limit * 1.6) + 5)).isoformat()
    resp = _run(
        ["data", "bars", "--symbol", symbol, "--timeframe", "1Day", "--start", start, "--limit", str(limit), "--sort", "desc"]
    )
    bars = resp.get("bars") or [] if isinstance(resp, dict) else resp
    return list(reversed(bars))


def list_option_expirations(symbol: str, dte_min: int, dte_max: int) -> list[str]:
    import datetime

    today = datetime.date.today()
    gte = (today + datetime.timedelta(days=dte_min)).isoformat()
    lte = (today + datetime.timedelta(days=dte_max)).isoformat()
    resp = _run(
        [
            "option", "contracts",
            "--underlying-symbols", symbol,
            "--expiration-date-gte", gte,
            "--expiration-date-lte", lte,
            "--limit", "1000",
        ]
    )
    contracts = resp.get("option_contracts", resp) if isinstance(resp, dict) else resp
    dates = sorted({c["expiration_date"] for c in contracts})
    return dates


def get_option_chain(symbol: str, expiration_date: str) -> dict:
    resp = _run(
        [
            "data", "option", "chain",
            "--underlying-symbol", symbol,
            "--expiration-date", expiration_date,
            "--limit", "1000",
        ]
    )
    return resp.get("snapshots", {}) if isinstance(resp, dict) else {}


def submit_credit_spread(short_symbol: str, long_symbol: str, qty: int, limit_credit: float, dry_run: bool) -> dict:
    """Net-credit limit order: won't fill for less than limit_credit, avoiding market-order slippage
    on multi-leg options where the quoted mid can move between decision time and execution."""
    legs = json.dumps(
        [
            {"symbol": short_symbol, "side": "sell", "ratio_qty": "1", "position_intent": "sell_to_open"},
            {"symbol": long_symbol, "side": "buy", "ratio_qty": "1", "position_intent": "buy_to_open"},
        ]
    )
    args = [
        "order", "submit",
        "--order-class", "mleg",
        "--qty", str(qty),
        "--type", "limit",
        "--limit-price", f"{limit_credit:.2f}",
        "--time-in-force", "day",
        "--legs", legs,
    ]
    if dry_run:
        args.append("--dry-run")
    return _run(args)
