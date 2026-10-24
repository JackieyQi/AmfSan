"""Small, validated strategy configurations; no arbitrary executable expressions."""
from decimal import Decimal, InvalidOperation
from models.strategy_rules import CONDITIONS, evaluate_condition

INTERVALS = {"1h": 3600, "4h": 14400, "1d": 86400}


def validate_strategy(data):
    if not isinstance(data, dict):
        raise ValueError("策略配置必须是对象")
    if set(data) - {"name", "buy", "sell"}:
        raise ValueError("存在不支持的策略字段")
    name = data.get("name")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 64:
        raise ValueError("策略名称须为 1–64 个字符")
    result = {"name": name.strip()}
    for direction in ("buy", "sell"):
        rule = data.get(direction)
        if rule is None:
            result[direction] = None
            continue
        if not isinstance(rule, dict) or set(rule) != {"op", "conditions"}:
            raise ValueError("规则必须包含组合方式和条件")
        if rule["op"] not in ("all", "any"):
            raise ValueError("仅支持全部满足或任意满足")
        conditions = rule["conditions"]
        if not isinstance(conditions, list) or not 1 <= len(conditions) <= 20:
            raise ValueError("每个方向需要 1–20 个条件")
        normalized = []
        for item in conditions:
            if isinstance(item, str):
                if item not in CONDITIONS:
                    raise ValueError("未知条件标识")
                normalized.append(item)
                continue
            if not isinstance(item, dict) or set(item) != {"indicator", "interval", "relation", "candle"}:
                raise ValueError("条件字段不正确；MACD 阈值固定为 0")
            if item["indicator"] != "macd" or item["interval"] not in INTERVALS:
                raise ValueError("仅支持 MACD 柱值及 1h、4h、1d 周期")
            if item["relation"] not in ("above_zero", "below_zero"):
                raise ValueError("仅支持零轴上方或下方")
            if item["candle"] not in ("closed", "current"):
                raise ValueError("请选择最近已收盘或当前 K 线")
            normalized.append(dict(item))
        result[direction] = {"op": rule["op"], "conditions": normalized}
    if result["buy"] is None and result["sell"] is None:
        raise ValueError("至少配置一个信号方向")
    return result


def evaluate_custom_strategy(definition, direction, candles_by_interval, now, model=None):
    """Future binding entrypoint. Rows belong to one symbol and contain opening_ts/macd.

    Library references use model factors; legacy rows use candles_by_interval.
    None means unavailable data; never coerce it to zero or a matching signal.
    The current monitoring scheduler deliberately does not call this function.
    """
    definition = validate_strategy(definition)
    if direction not in ("buy", "sell"):
        raise ValueError("Unknown direction")
    rule = definition[direction]
    if rule is None:
        return False
    results = []
    for condition in rule["conditions"]:
        if isinstance(condition, str):
            if model is None:
                raise ValueError("条件库规则需要传入已初始化因子的 model")
            results.append(evaluate_condition(condition, model, now))
            continue
        seconds = INTERVALS[condition["interval"]]
        expected = int(now) // seconds * seconds
        if condition["candle"] == "closed":
            expected -= seconds
        rows = candles_by_interval.get(condition["interval"], [])
        row = next((r for r in rows if r.opening_ts == expected), None)
        if row is None or row.macd is None:
            return None
        try:
            value = Decimal(str(row.macd))
        except (InvalidOperation, ValueError):
            return None
        if not value.is_finite():
            return None
        results.append(value > 0 if condition["relation"] == "above_zero" else value < 0)
    if rule["op"] == "all":
        return False if False in results else None if None in results else True
    return True if True in results else None if None in results else False
