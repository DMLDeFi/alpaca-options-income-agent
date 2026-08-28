# Options Income Agent — Alpaca AI Trading Agents Hackathon

An autonomous options-trading agent built on Alpaca's paper-trading API for the
[Alpaca AI Trading Agents Hackathon](https://lablab.ai) (lablab.ai x Alpaca, 28 Aug–4 Sep 2026).

## The problem

Options trading rewards consistency under stress: tracking volatility, sizing positions, and
enforcing risk limits without emotion, continuously. Humans are usually fine at picking a
direction — they're bad at reacting instantly when a risk limit is breached and staying
disciplined instead of over-riding their own rules. That's a computation and discipline problem,
which is exactly what an agent is suited to solve.

## The strategy

**Defined-risk options income, sized by realized volatility, with a small capped allocation for
high-conviction directional plays.** Rather than betting on direction, the agent sells credit
spreads (bull put spreads / bear call spreads) roughly one standard deviation out of the money —
the statistically higher win-rate zone — and collects premium as those options decay. Every trade
has a hard-capped maximum loss defined at entry (the spread width minus the credit received), so a
single bad outcome can't meaningfully damage the account.

## Architecture

```
run_agent.py         orchestrates one decision cycle (meant to be run on a schedule)
├── alpaca_cli.py     wraps Alpaca's official CLI (data, orders, account) — no raw HTTP calls
├── strategy.py       scans the universe, builds candidate credit spreads from live option chains
├── risk_gates.py     hard-coded caps: max loss/trade, max total open risk, position count, daily circuit breaker
├── brain.py          reasoning step — shells out to the Claude Code CLI (`claude -p`), authenticated
│                     via a Claude Pro/Max subscription token rather than a pay-per-token API key, to
│                     judge trade quality among pre-approved candidates; falls back to a transparent
│                     rule-based check if no token is configured or the call fails
└── state.py          tracks open positions' committed risk across cycles
```

**Risk gates run before the reasoning step, not after.** `risk_gates.py` filters the raw candidate
list down to only what's already within the account's risk budget — position size cap, total open
risk cap, and position-count cap — before the AI reasoning step (`brain.py`) ever sees them. The
reasoning step can reject a candidate or rank it, but it can never approve something that would
breach a gate, because anything over the line was already dropped. A daily circuit breaker also
halts all new entries for the day if the account is down more than the configured threshold from
the prior close.

## Why the Alpaca CLI (not just the SDK)

The submitted agent uses Alpaca's official CLI (`alpaca` binary, github.com/alpacahq/cli) for every
data pull and order — market data, option chains, account state, and multi-leg order submission.
The CLI is what Alpaca's own docs recommend for unattended/scheduled agent runs (their MCP server is
built for an interactive assistant trading alongside a human — the CLI is built for cron jobs and
long-running agent sessions, which is what this is). The Alpaca MCP server is also configured in
this repo (`.mcp.json`) and used during development to inspect the account and test trades
interactively from inside an AI coding assistant.

## Setup

1. `cp .env.example .env` and fill in your own Alpaca **paper** API key/secret (see [Alpaca docs](https://docs.alpaca.markets/us/docs/getting-started)).
   Optionally run `claude setup-token` (requires a Claude Pro/Max subscription and a real terminal —
   it opens a browser to authenticate) and put the resulting token in `CLAUDE_CODE_OAUTH_TOKEN` for
   live LLM reasoning — without it, the agent runs on a transparent rule-based fallback instead.
2. Install [uv](https://docs.astral.sh/uv/), then:
   ```bash
   uv venv .venv
   uv pip install -r requirements.txt --python .venv
   ```
3. Install the [Alpaca CLI](https://github.com/alpacahq/cli) and make sure `alpaca` is on your PATH
   (or set `ALPACA_CLI_PATH` in `.env` to its full path).
4. Run one decision cycle:
   ```bash
   .venv/Scripts/python.exe src/run_agent.py   # Windows
   .venv/bin/python src/run_agent.py           # macOS/Linux
   ```

`AGENT_DRY_RUN=true` in `.env` previews every order without submitting it — flip to `false` only
once you've reviewed a few dry-run cycles.

## Disclaimer

Built and tested exclusively in Alpaca's paper-trading environment. Nothing here is investment
advice; paper-trading results are simulated and do not represent real trading or future performance.
