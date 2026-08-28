import json
import os
import subprocess

from config import CLAUDE_CLI_PATH, CLAUDE_CODE_OAUTH_TOKEN

SYSTEM_PROMPT = """You are the trading-decision component of an autonomous options-income agent \
running on Alpaca paper trading. You are shown a list of PRE-APPROVED defined-risk credit-spread \
candidates — every candidate has already passed hard-coded risk gates (max loss per trade, total \
open-risk cap, position count cap), so you cannot make the agent take on more risk than it already \
has been cleared for.

Strategy context, important: this agent deliberately sells strikes roughly ONE STANDARD DEVIATION \
out of the money (about 16-delta) rather than the 30-40 delta strikes a typical premium-selling \
trader uses. That's a conscious choice for a higher win rate on defined-risk trades, and it means \
credit-to-width will structurally run lower than a 30-40 delta spread would produce — the coded \
floor for this strategy is 7% credit-to-width, calibrated from what real 1-stddev spreads on this \
account actually pay. Do NOT apply a generic options-trader's 25-33%+ credit-to-width expectation; \
that reference point assumes closer-to-the-money strikes this strategy intentionally avoids. Judge \
candidates against the 7% floor context, not a generic heuristic.

What you SHOULD still reject: candidates with internally inconsistent numbers (e.g. credit close to \
or exceeding spread width — that's stale/bad quote data, not a real price), redundant exposure to \
the same underlying/expiration as another candidate you're approving, or credit-to-width so far \
below the 7% floor's spirit that it's clearly not worth the tail risk. Explain your reasoning in the \
voice of a disciplined options-income trader who understands why this strategy trades this way.

Respond with strict JSON only, no other text: {"decisions": [{"index": int, "approve": bool, "reason": string}, ...]}"""


def _rule_based_fallback(candidates: list, cfg) -> list[dict]:
    decisions = []
    seen_symbols = set()
    bar = cfg.min_credit_to_width
    for i, c in enumerate(candidates):
        dup = c.symbol in seen_symbols
        approve = (not dup) and c.credit_to_width >= bar
        reason = (
            f"Rule-based fallback: credit/width {c.credit_to_width:.0%} "
            f"{'meets' if c.credit_to_width >= bar else 'below'} the {bar:.0%} income bar"
            + (", but skipped — already have a position on this underlying today" if dup else "")
        )
        decisions.append({"index": i, "approve": approve, "reason": reason})
        if approve:
            seen_symbols.add(c.symbol)
    return decisions


def _call_claude_cli(prompt: str) -> str:
    """Prompt goes over stdin rather than as a CLI argument — Windows mangles complex
    JSON/quoting when a .cmd shim's arguments get relayed through cmd.exe."""
    env = {**os.environ}
    if CLAUDE_CODE_OAUTH_TOKEN:
        env["CLAUDE_CODE_OAUTH_TOKEN"] = CLAUDE_CODE_OAUTH_TOKEN
    result = subprocess.run(
        [CLAUDE_CLI_PATH, "-p", "--restricted", "--max-budget-usd", "0.20"],
        input=prompt,
        capture_output=True,
        text=True,
        env=env,
        timeout=90,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "claude CLI call failed")
    return result.stdout


def decide(candidates: list, account: dict, cfg) -> list[dict]:
    if not candidates:
        return []
    if not CLAUDE_CODE_OAUTH_TOKEN:
        return _rule_based_fallback(candidates, cfg)

    try:
        payload = {
            "account_equity": account["equity"],
            "risk_gates_already_applied": {
                "max_risk_per_trade_pct": cfg.max_risk_per_trade_pct,
                "max_total_open_risk_pct": cfg.max_total_open_risk_pct,
                "max_open_positions": cfg.max_open_positions,
            },
            "candidates": [
                {
                    "index": i,
                    "symbol": c.symbol,
                    "kind": c.kind,
                    "expiration": c.expiration,
                    "short_leg": c.short_leg,
                    "long_leg": c.long_leg,
                    "credit": c.credit,
                    "width": c.width,
                    "max_loss": c.max_loss,
                    "credit_to_width": c.credit_to_width,
                }
                for i, c in enumerate(candidates)
            ],
        }
        prompt = SYSTEM_PROMPT + "\n\n" + json.dumps(payload)
        text = _call_claude_cli(prompt)
        parsed = json.loads(text[text.index("{"):text.rindex("}") + 1])
        return parsed["decisions"]
    except Exception as exc:
        print(f"[brain] Claude Code CLI reasoning failed ({exc}); falling back to rule-based decisions")
        return _rule_based_fallback(candidates, cfg)
