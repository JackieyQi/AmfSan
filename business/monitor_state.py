"""Read-only monitor state and action availability for API consumers."""
from decimal import Decimal

from business.spot_holdings import SPOT_MODEL, DEFAULT_SPOT_MODEL, position, min_holding_usdt, buy_blocked

STATE_TEXT = {
    "monitoring": "监控中", "paused": "已暂停", "needs_configuration": "待配置",
    "holding_blocks_buy": "持仓已达下限，买入已暂停",
    "unsupported_account": "该账户不支持现货卖出监控", "unconfigured": "未配置币安密钥",
    "pending": "等待持仓同步", "config_mismatch": "后端密钥配置不一致",
    "error": "持仓同步失败", "stale": "持仓数据已过期",
    "unsupported_symbol": "不支持的 USDT 现货交易对", "no_holding": "没有现货持仓",
    "valuation_unavailable": "持仓估值不可用", "below_minimum": "持仓低于监控门槛",
}


def monitor_capabilities(viewer, owner=None):
    owner = viewer if owner is None else owner
    return {"can_view_spot": viewer == "root",
            "allowed_directions": ["buy", "sell"] if viewer == owner == "root" else ["buy"]}


def monitor_state(row, viewer, snapshot, config_error=None):
    manage = viewer == "root" or viewer == row.user_id
    holding = position(snapshot, row.symbol) if row.user_id == "root" else None
    state, reason = "monitoring", ""
    if row.monitor_direction == "buy":
        if buy_blocked(row.user_id, row.symbol, snapshot):
            state, reason = "holding_blocks_buy", "该币种持仓已达到全局下限，买入提醒停止，持仓同步将删除买入配置并创建卖出监控"
        elif config_error:
            state, reason = "needs_configuration", config_error
    elif row.user_id != "root":
        state, reason = "unsupported_account", "币安现货卖出监控仅限 root 使用"
    else:
        state = snapshot.get("status", "pending")
        if state != "ok":
            state = state if state in STATE_TEXT else "error"
            reason = STATE_TEXT[state]
        else:
            if holding is None:
                state = "unsupported_symbol"
            elif Decimal(holding["total"]) <= 0:
                state = "no_holding"
            elif holding["value_usdt"] is None:
                state = "valuation_unavailable"
            elif not holding["eligible"]:
                state = "below_minimum"
            elif row.strategy_model_key not in (SPOT_MODEL, DEFAULT_SPOT_MODEL) or config_error:
                state, reason = "needs_configuration", config_error or "请重新选择卖出模型"
            else:
                state = "monitoring"
            if not reason:
                reason = (f"持仓估值低于 {min_holding_usdt()} USDT 监控门槛" if state == "below_minimum"
                          else STATE_TEXT[state] if state != "monitoring" else "")

    def action(allowed, blocked_reason):
        return {"allowed": manage and allowed,
                "reason": "无权操作该监控" if not manage else "" if allowed else blocked_reason}

    # Removal is safe only when a fresh, supported balance confirms zero.
    can_delete = row.monitor_direction == "buy" or row.user_id != "root" or (holding is not None and Decimal(holding["total"]) == 0)
    status = state if row.is_valid else "paused"
    return {
        "status": status, "status_text": STATE_TEXT[status],
        "readiness_status": state, "blocked_reason": reason,
        "holding": holding,
        "allowed_directions": monitor_capabilities(viewer, row.user_id)["allowed_directions"] if manage else [],
        "actions": {
            "edit": action(row.monitor_direction == "buy" or row.user_id == "root", "无权编辑该监控"),
            "delete": action(can_delete, "持仓存在或状态未确认，请使用暂停"),
            "pause": action(row.is_valid, "监控已暂停或停用"),
            "resume": action(not row.is_valid and state == "monitoring",
                             "监控已启用" if row.is_valid else reason),
        },
    }
