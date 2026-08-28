import state


def daily_circuit_breaker_tripped(account: dict, cfg) -> tuple[bool, str]:
    equity = float(account["equity"])
    last_equity = float(account["last_equity"])
    if last_equity <= 0:
        return False, ""
    daily_pl_pct = (equity - last_equity) / last_equity
    if daily_pl_pct <= -cfg.daily_loss_circuit_breaker_pct:
        return True, f"Daily loss {daily_pl_pct:.2%} breached -{cfg.daily_loss_circuit_breaker_pct:.0%} circuit breaker"
    return False, ""


def filter_candidates(candidates: list, account: dict, cfg) -> list:
    """Hard gates enforced in code — the reasoning step downstream can only reject or rank
    within this pre-vetted list, never approve something that violates these caps."""
    equity = float(account["equity"])
    max_loss_per_trade = equity * cfg.max_risk_per_trade_pct
    remaining_total_risk = equity * cfg.max_total_open_risk_pct - state.total_open_risk()
    remaining_slots = cfg.max_open_positions - state.open_position_count()

    approved = []
    for c in candidates:
        if remaining_slots <= 0:
            break
        if c.max_loss > max_loss_per_trade:
            continue
        if c.max_loss > remaining_total_risk:
            continue
        approved.append(c)
        remaining_total_risk -= c.max_loss
        remaining_slots -= 1
    return approved
