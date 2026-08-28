import math
import re
from dataclasses import dataclass

import alpaca_cli as api

OCC_RE = re.compile(r"^([A-Z]+)(\d{6})([CP])(\d{8})$")


def parse_occ(symbol: str):
    m = OCC_RE.match(symbol)
    if not m:
        return None
    root, _, opt_type, strike_raw = m.groups()
    return {"root": root, "type": "call" if opt_type == "C" else "put", "strike": int(strike_raw) / 1000}


def realized_vol_annualized(bars: list) -> float:
    closes = [b["c"] for b in bars if b.get("c")]
    if len(closes) < 5:
        return 0.0
    log_returns = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
    mean = sum(log_returns) / len(log_returns)
    variance = sum((r - mean) ** 2 for r in log_returns) / (len(log_returns) - 1)
    return math.sqrt(variance) * math.sqrt(252)


def mid_price(quote_snapshot: dict) -> float | None:
    q = quote_snapshot.get("latestQuote", {})
    bid, ask = q.get("bp", 0), q.get("ap", 0)
    if not bid or not ask:
        return None
    return (bid + ask) / 2


def strikes_by_proximity(chain: dict, opt_type: str, target_strike: float, exclude: set[str] = frozenset()) -> list[str]:
    candidates = []
    for sym in chain:
        if sym in exclude:
            continue
        parsed = parse_occ(sym)
        if not parsed or parsed["type"] != opt_type:
            continue
        candidates.append((abs(parsed["strike"] - target_strike), sym))
    candidates.sort()
    return [sym for _, sym in candidates]


def find_quoted_strike(chain: dict, opt_type: str, target_strike: float, exclude: set[str] = frozenset(), tries: int = 5) -> str | None:
    """Nearest strike to target that actually has a live bid/ask — the paper options feed
    leaves many far/illiquid strikes with empty quotes, so we can't just take the single closest."""
    for sym in strikes_by_proximity(chain, opt_type, target_strike, exclude)[:tries]:
        if mid_price(chain[sym]) is not None:
            return sym
    return None


@dataclass
class SpreadCandidate:
    symbol: str
    expiration: str
    kind: str  # "put_credit" or "call_credit"
    short_leg: str
    long_leg: str
    credit: float
    width: float
    max_loss: float
    credit_to_width: float


def build_income_candidates(symbol: str, cfg) -> list[SpreadCandidate]:
    underlying_price = api.get_latest_stock_price(symbol)
    bars = api.get_daily_bars(symbol, limit=30)
    vol = realized_vol_annualized(bars)
    if vol <= 0:
        return []

    expirations = api.list_option_expirations(symbol, cfg.target_dte_min, cfg.target_dte_max)
    if not expirations:
        return []
    expiration = expirations[len(expirations) // 2]  # roughly middle of the target DTE window

    import datetime
    dte = (datetime.date.fromisoformat(expiration) - datetime.date.today()).days
    stddev_move = underlying_price * vol * math.sqrt(dte / 365)
    width = round(max(underlying_price * cfg.spread_width_pct, 1.0))

    chain = api.get_option_chain(symbol, expiration)
    if not chain:
        return []

    candidates = []
    for opt_type, direction in (("put", -1), ("call", 1)):
        target_short = underlying_price + direction * cfg.short_strike_stddev * stddev_move
        short_sym = find_quoted_strike(chain, opt_type, target_short)
        if not short_sym:
            continue
        short_strike = parse_occ(short_sym)["strike"]
        target_long = short_strike + direction * width
        long_sym = find_quoted_strike(chain, opt_type, target_long, exclude={short_sym})
        if not long_sym:
            continue
        long_strike = parse_occ(long_sym)["strike"]
        actual_width = abs(long_strike - short_strike)
        if actual_width <= 0:
            continue

        short_mid = mid_price(chain[short_sym])
        long_mid = mid_price(chain[long_sym])

        credit = round(short_mid - long_mid, 2)
        # Credit can never legitimately exceed the spread width (that would be riskless arbitrage);
        # this paper-trading feed occasionally returns stale/crossed quotes, so treat it as bad data.
        if credit <= 0 or credit >= actual_width:
            continue
        max_loss = round((actual_width - credit) * 100, 2)  # option contracts are per 100 shares
        credit_to_width = credit / actual_width
        if credit_to_width < cfg.min_credit_to_width:
            continue

        candidates.append(
            SpreadCandidate(
                symbol=symbol,
                expiration=expiration,
                kind=f"{opt_type}_credit",
                short_leg=short_sym,
                long_leg=long_sym,
                credit=credit,
                width=actual_width,
                max_loss=max_loss,
                credit_to_width=round(credit_to_width, 3),
            )
        )
    return candidates


def scan_universe(cfg) -> list[SpreadCandidate]:
    all_candidates = []
    for symbol in cfg.universe:
        try:
            all_candidates.extend(build_income_candidates(symbol, cfg))
        except Exception as exc:
            print(f"[scan] skipping {symbol}: {exc}")
    return sorted(all_candidates, key=lambda c: c.credit_to_width, reverse=True)
