# Options Income Agent — One-Page Write-Up

**Alpaca AI Trading Agents Hackathon (lablab.ai x Alpaca), 28 Aug–4 Sep 2026**
Alpaca paper account: `PA3W1Q2MFEZ8` · Repo: github.com/DMLDeFi/alpaca-options-income-agent

## The problem

Options trading rewards consistency under stress — tracking volatility, sizing positions, and
enforcing risk limits continuously, without emotion. Most retail traders aren't bad at picking a
direction; they're bad at reacting the instant a risk limit is breached and staying disciplined
instead of overriding their own rules. That's a computation and discipline problem, which is what
an agent is actually suited to solve — so this project builds one, rather than another
signal-generation bot chasing direction.

## AI logic

The agent scans a liquid universe (SPY, QQQ, IWM, DIA, AAPL, MSFT, NVDA, AMZN, GOOGL, META, TSLA,
AMD, NFLX, JPM, XOM) each cycle and builds defined-risk credit spreads roughly one standard
deviation out of the money — sized off each name's own realized volatility rather than a fixed
distance, since a flat dollar or percentage offset means something very different for a 30%-vol
stock than a 15%-vol one. That distance is a deliberate choice: it's the higher win-rate zone for
premium selling, at the cost of a lower credit-to-width ratio than a closer-to-the-money spread
would pay.

Every candidate that survives the hard-coded risk gates (below) is handed to Claude, invoked
through the Claude Code CLI, as the reasoning layer. Claude doesn't decide *how much* risk to take —
that's already capped before it sees anything — it judges *trade quality*: is the credit worth the
tail risk for this specific strategy's economics, is this candidate internally consistent (real
option markets never let credit exceed spread width — a violation means bad/stale quote data, not
a live price), and does approving it create redundant exposure to a name/expiration the agent is
already committed to elsewhere. In testing, this caught real cases a naive rules engine would have
missed: it flagged mathematically-impossible quotes from this data feed as bad data rather than
trading them, and repeatedly declined a second spread on the same underlying/expiration in favor of
keeping the better-paying one, treating a portfolio as a portfolio rather than a pile of
independent bets.

## Risk gates

Enforced in code, before the reasoning step ever runs — Claude can reject or rank what it's shown,
but nothing it approves can breach a gate that already excluded it:

- **Max loss per trade**: capped at 3% of account equity
- **Max total open risk**: sum of every open position's max loss capped at 15% of equity
- **Max concurrent positions**: 6
- **Daily circuit breaker**: halts all new entries for the day if equity is down more than 5% from
  the prior close
- **Data-sanity guard**: any spread where credit ≥ width is discarded outright as a stale quote,
  never reaching either the AI reasoning step or an order

## Alpaca infrastructure

All data (option chains, historical bars, quotes) and order execution (multi-leg credit spreads,
net-credit limit orders) run through **Alpaca's official CLI**, not a raw SDK — the CLI is what
Alpaca's own docs recommend for unattended, scheduled agent runs, as opposed to the MCP server,
which is built for an interactive assistant trading alongside a human. The Alpaca MCP server is
also wired into this repo and was used throughout development to inspect the account and test
trades interactively from inside an AI coding assistant. The agent runs autonomously on a schedule
throughout the competition window, not on manual trigger.

## Disclaimer

Built and tested exclusively in Alpaca's paper-trading environment. Nothing here is investment
advice; paper-trading results are simulated and do not represent real trading or future performance.
