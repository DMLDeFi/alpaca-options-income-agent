import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

ALPACA_BIN = os.environ.get("ALPACA_CLI_PATH", "alpaca")
ALPACA_API_KEY = os.environ["ALPACA_API_KEY"]
ALPACA_SECRET_KEY = os.environ["ALPACA_SECRET_KEY"]

# Reasoning step runs through the Claude Code CLI, authenticated via a Pro/Max subscription
# token (from `claude setup-token`) rather than a separate pay-per-token API key.
CLAUDE_CLI_PATH = os.environ.get("CLAUDE_CLI_PATH", "claude")
CLAUDE_CODE_OAUTH_TOKEN = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "")

# Master safety switch: while true, orders are built and logged but never sent to Alpaca.
AGENT_DRY_RUN = os.environ.get("AGENT_DRY_RUN", "true").lower() == "true"

LOG_DIR = PROJECT_ROOT / "logs"
STATE_FILE = PROJECT_ROOT / "logs" / "state.json"


@dataclass
class RiskConfig:
    # Broad but liquid/optionable universe — bid/ask spreads on the option legs stay tight,
    # and scanning more names gives Claude's reasoning step more chances to find a setup that
    # clears its own bar without loosening the strike-selection discipline itself.
    universe: list[str] = field(
        default_factory=lambda: [
            "SPY", "QQQ", "IWM", "DIA",
            "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AMD", "NFLX", "JPM", "XOM",
        ]
    )

    # Defined-risk income trades: how far out and how wide.
    target_dte_min: int = 7
    target_dte_max: int = 21
    short_strike_stddev: float = 1.0  # short strike placed ~1 std-dev move away (approx 16-delta, high win-rate)
    spread_width_pct: float = 0.015  # long leg strike ~1.5% of underlying further out

    # A credit spread must collect at least this fraction of its width to be worth the defined risk.
    # Calibrated to ~1-stddev-OTM economics (observed 6-9% in practice) rather than the ~20%+ typical
    # of much closer, lower-win-rate strikes — going closer to the money to chase a bigger ratio would
    # undercut the whole point of picking a high win-probability strike in the first place.
    min_credit_to_width: float = 0.07

    # Hard risk gates enforced in code regardless of what the reasoning step recommends.
    max_risk_per_trade_pct: float = 0.03  # max loss on any single spread, as % of equity
    max_total_open_risk_pct: float = 0.15  # sum of max-loss across all open spreads, as % of equity
    max_open_positions: int = 6
    daily_loss_circuit_breaker_pct: float = 0.05  # halt new entries if today's equity is down this much

    # Opportunistic directional bucket: small, capped, only for high-conviction setups.
    opportunistic_allocation_pct: float = 0.10  # max % of equity ever committed to directional debit spreads
    opportunistic_vol_spike_ratio: float = 1.3  # recent realized vol vs longer-run realized vol
    opportunistic_momentum_pct: float = 0.015  # min 1-day move to count as momentum confirmation


RISK = RiskConfig()
