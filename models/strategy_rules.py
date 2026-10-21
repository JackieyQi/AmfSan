"""Code-owned condition library and rule trees shared by execution and display.

Only trusted definitions in this module are executable. This is not a user-code
or expression evaluator. Candle index 0 is the current, possibly open candle.

Manual changes: edit CONDITIONS for parameters and TOP_RISE for composition.
Increment TOP_RISE.version when changing rule semantics. Decimal parameters are
stored as strings for lossless JSON display. Helpers in factor.py retain their
existing window semantics; review_note records unresolved intent.
"""
from copy import deepcopy
from decimal import Decimal


def condition(name, factor, method=None, params=None, indices=None,
              minimum=1, negate=False, field=None, comparison=None, value=None,
              description="", candle_scope="", review_note=None):
    return dict(name=name, factor=factor, method=method, params=params or {},
                indices=indices, minimum=minimum, negate=negate, field=field,
                comparison=comparison, value=value, description=description,
                candle_scope=candle_scope, review_note=review_note)


CONDITIONS = {
    "price_guard": condition("4h 价格过热过滤", "kline_4h_factors",
        "is_curr_price_away_from_bbupper", {"tolerance": "0.01"}, [0, 1], negate=True,
        description="两根收盘价均未超过各自布林上轨的 1%。", candle_scope="当前及前一根 4h K 线"),
    "daily_trend": condition("日线 EMA 多头排列", "kline_1d_factors",
        "is_ema_bullish_stack", {"index": 0, "window_size": 1},
        description="EMA12 > EMA26。", candle_scope="当前日线，可能未收盘"),
    "bullish_ratio": condition("4h 阳线比例", "kline_4h_factors",
        "is_bullish_k", indices=[1, 2, 3, 4], minimum=3,
        description="前四根至少三根阳线（原规则为比例 ≥ 70%）。", candle_scope="前四根已收盘 4h K 线"),
    "above_ema": condition("4h 连续站上 EMA12", "kline_4h_factors",
        "is_ema12_continue_lt_close", {"index": 1, "window_size": 3},
        description="连续三根收盘价 > 对应 EMA12。", candle_scope="前三根已收盘 4h K 线"),
    "near_upper": condition("4h 贴近布林上轨", "kline_4h_factors",
        "is_near_upper", {"tolerance": "0.03"}, [1, 2, 3], minimum=2,
        description="三根至少两根满足：收盘价不低于中轨，且（上轨－收盘价）/（上轨－中轨）≤ 0.03。", candle_scope="前三根已收盘 4h K 线"),
    "widen": condition("4h 布林带宽扩大", "kline_4h_factors",
        "is_boll_widen", {"index": 1, "window_size": 3},
        description="比较索引 1→2、2→3、3→4、4→5，连续四次带宽扩大。", candle_scope="前五根已收盘 4h K 线",
        review_note="原函数 window_size=3 实际比较四次；保留现有行为，是否改为三次需手动决定。"),
    "hour_bullish": condition("1h 连续阳线", "kline_1h_factors",
        "is_bullish_k", indices=[0, 1, 2], minimum=3,
        description="最近三根全部为阳线。", candle_scope="包含当前未收盘 1h K 线"),
    "hour_upper": condition("1h 沿布林上轨", "kline_1h_factors",
        "is_along_upper_band", {"n": 3, "tolerance": "0.2"},
        description="最近三根至少两根贴轨；距离按上轨与中轨之间的宽度归一化，容差 0.2。", candle_scope="包含当前未收盘 1h K 线",
        review_note="原注释写连续三根，实际只需两根；容差不是币价的 20%。保留实际行为。"),
    "macd_down": condition("4h MACD 连续减小", "macd_4h_factors",
        "is_continue_down", {"index": 0, "window_size": 3},
        description="最近三个 MACD 值按时间顺序严格递减。", candle_scope="包含当前未收盘 4h K 线"),
    "kdj_cross": condition("4h KDJ 死叉", "kdj_4h_factors",
        "is_death_cross", indices=[0, 1],
        description="当前或前一根出现 K 下穿 D。", candle_scope="触发位置为当前或前一根；交叉还读取更早一根"),
    "j_down": condition("4h J 值连续下行", "kdj_4h_factors",
        "is_j_continue_down", {"index": 0, "window_size": 2},
        description="最近三个 J 值按时间顺序连续两次严格下降。", candle_scope="包含当前未收盘 4h K 线"),
    "j_low": condition("4h 当前 J 值低于阈值", "kdj_4h_factors",
        field="kdj_list.j_val", comparison="lt", value="70", indices=[0], candle_scope="当前 4h K 线"),
    "rsi_speed": condition("4h RSI 变化加速", "rsi_4h_factors",
        "is_fast_down", {"threshold": "1.3"}, [0, 1],
        description="当前或前一根 RSI 绝对变化量超过此前四次绝对变化均值的 1.3 倍。", candle_scope="包含当前 4h K 线，最远读取索引 6",
        review_note="is_fast_down 实际使用绝对变化量，快速上涨也可能满足；本次不改为仅下跌。"),
    "rsi_low": condition("4h 当前 RSI 低于阈值", "rsi_4h_factors",
        field="rsi_list.rsi", comparison="lt", value="70", indices=[0], candle_scope="当前 4h K 线"),
    "engulfing": condition("4h 看跌吞没", "kline_4h_factors",
        "is_bearish_engulfing_k", indices=[0, 1], candle_scope="当前或前一根；形态还读取更早一根"),
    "high_away": condition("4h 最高价远离上轨", "kline_4h_factors",
        "is_high_price_away_from_bbupper", {"tolerance": "0.08"}, [0, 1],
        description="当前或前一根最高价超过对应上轨的 8%。", candle_scope="当前及前一根 4h K 线"),
    "rsi_high": condition("4h RSI 高位", "rsi_4h_factors",
        field="rsi_list.rsi", comparison="gt", value="85", indices=[0, 1],
        description="当前或前一根 RSI > 85。", candle_scope="当前及前一根 4h K 线",
        review_note="最高价远离上轨和 RSI > 85 可以发生在不同 K 线上，沿用原逻辑。"),
}


def group(op, *children, **kwargs):
    return dict(op=op, children=list(children), **kwargs)


TOP_RISE = {
    "key": "model_top_rise",
    "name": "布林贴顶加速上涨模型",
    "version": "1",
    "status": "当前监控使用",
    "summary": "日线趋势过滤，4h 强势结构确认，1h 入场触发。买入和卖出分别使用以下规则。",
    "entry": group("all", "price_guard", "daily_trend", "bullish_ratio", "above_ema",
                   "near_upper", "widen", group("any", "hour_bullish", "hour_upper")),
    "exit": group("all",
        group("at_least", "macd_down", group("all", "kdj_cross", "j_down", "j_low"),
              group("all", "rsi_speed", "rsi_low"), minimum=2),
        group("any", "engulfing", group("all", "high_away", "rsi_high"), "kdj_cross")),
}


def evaluate_condition(key, model):
    definition = CONDITIONS[key]
    factor = getattr(model, definition["factor"])
    params = {k: Decimal(v) if isinstance(v, str) else v
              for k, v in definition["params"].items()}

    def check(index):
        if definition["field"]:
            collection, field = definition["field"].split(".")
            actual = getattr(getattr(factor, collection)[index], field)
            target = Decimal(definition["value"])
            if definition["comparison"] == "lt":
                return actual < target
            if definition["comparison"] == "gt":
                return actual > target
            raise ValueError("Unsupported comparison")
        arguments = dict(params)
        if index is not None:
            arguments["index"] = index
        return getattr(factor, definition["method"])(**arguments)

    values = [check(i) for i in (definition["indices"] or [None])]
    matched = sum(bool(v) for v in values) >= definition["minimum"]
    return not matched if definition["negate"] else matched


def evaluate_rule(rule, model):
    if isinstance(rule, str):
        return evaluate_condition(rule, model)
    children = rule["children"]
    if rule["op"] == "all":
        return all(evaluate_rule(child, model) for child in children)
    if rule["op"] == "any":
        return any(evaluate_rule(child, model) for child in children)
    if rule["op"] == "at_least":
        return sum(evaluate_rule(child, model) for child in children) >= rule["minimum"]
    raise ValueError("Unsupported rule operator")


def get_strategy_definitions():
    return deepcopy({"conditions": CONDITIONS, "models": [TOP_RISE]})
