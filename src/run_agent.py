import datetime
import json

import alpaca_cli as api
import brain
import publish
import risk_gates
import state
import strategy
from config import AGENT_DRY_RUN, LOG_DIR, RISK


def log_cycle(record: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_DIR / "agent_log.jsonl", "a") as f:
        f.write(json.dumps(record) + "\n")


def run_cycle() -> dict:
    started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    account = api.get_account()
    clock = api.get_clock()
    positions = api.get_positions()
    state.reconcile_with_positions(positions)

    record = {"timestamp": started_at, "equity": account["equity"], "dry_run": AGENT_DRY_RUN}

    if not clock.get("is_open", False):
        record["status"] = "skipped_market_closed"
        log_cycle(record)
        print("Market is closed — no action taken this cycle.")
        return record

    tripped, reason = risk_gates.daily_circuit_breaker_tripped(account, RISK)
    if tripped:
        record["status"] = "halted_circuit_breaker"
        record["reason"] = reason
        log_cycle(record)
        print(f"CIRCUIT BREAKER: {reason}. No new entries today.")
        return record

    raw_candidates = strategy.scan_universe(RISK)
    approved_candidates = risk_gates.filter_candidates(raw_candidates, account, RISK)
    decisions = brain.decide(approved_candidates, account, RISK)

    executed = []
    for d in decisions:
        c = approved_candidates[d["index"]]
        entry = {
            "symbol": c.symbol,
            "kind": c.kind,
            "short_leg": c.short_leg,
            "long_leg": c.long_leg,
            "credit": c.credit,
            "max_loss": c.max_loss,
            "approved": d["approve"],
            "reason": d["reason"],
        }
        if d["approve"]:
            order = api.submit_credit_spread(c.short_leg, c.long_leg, qty=1, limit_credit=c.credit, dry_run=AGENT_DRY_RUN)
            entry["order"] = order
            if not AGENT_DRY_RUN:
                state.record_open_trade(
                    {
                        "symbol": c.symbol,
                        "short_leg": c.short_leg,
                        "long_leg": c.long_leg,
                        "max_loss": c.max_loss,
                        "opened_at": started_at,
                    }
                )
        executed.append(entry)

    record["status"] = "ran"
    record["candidates_found"] = len(raw_candidates)
    record["candidates_risk_approved"] = len(approved_candidates)
    record["decisions"] = executed
    log_cycle(record)

    print(f"Scanned {len(raw_candidates)} candidates, {len(approved_candidates)} passed risk gates.")
    for e in executed:
        flag = "ENTERED" if e["approved"] else "skipped"
        print(f"  [{flag}] {e['symbol']} {e['kind']}  credit=${e['credit']}  max_loss=${e['max_loss']}  — {e['reason']}")
    return record


if __name__ == "__main__":
    try:
        run_cycle()
    except Exception as exc:
        # A network blip or transient API error shouldn't produce a bare crash with no
        # record of what happened — log it as a distinct cycle status instead.
        log_cycle(
            {
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "status": "error",
                "reason": str(exc),
            }
        )
        print(f"Cycle failed: {exc}")
    finally:
        try:
            publish.write_status()
        except Exception as exc:
            print(f"Could not publish status (likely no network): {exc}")
