#! /usr/bin/env python
# coding:utf8

"""
Read-only signal catalog for admin display.

This module describes the current signal/factor vocabulary. It is not used by
strategy execution and must not become the source of truth for signal decisions.
"""


SIGNAL_RECORD_STATUS_TEXT = {
    0: "入场信号待确认",
    1: "入场信号已记录，等待出场信号",
    2: "入场信号失效",
    3: "出场信号待确认",
    4: "出场信号已记录",
    5: "出场信号按当前价记录",
}


SIGNAL_CATALOG = {
    "schema_version": "2026-04-19",
    "system_role": "automatic_signal_notification",
    "notes": [
        "This catalog is for admin display only.",
        "It does not place orders and does not drive strategy execution.",
        "The executable strategy source remains business/strategy.py and models/strategy.py.",
    ],
    "signal_categories": [
        {
            "key": "strategy_entry",
            "name": "策略入场信号",
            "status": "live",
            "description": "策略模型判断出现入场机会，发送买入信号通知并记录模拟入场。",
        },
        {
            "key": "strategy_exit",
            "name": "策略出场信号",
            "status": "live",
            "description": "策略模型、止盈或止损逻辑触发出场通知，并更新模拟出场记录。",
        },
        {
            "key": "price_limit_alert",
            "name": "价格阈值提醒",
            "status": "live",
            "description": "当前价格触达 Redis 中的低/高价阈值时发送提醒。",
        },
        {
            "key": "candidate_discovery",
            "name": "候选发现提醒",
            "status": "live",
            "description": "候选币或已关注币种突破近期高点，只做候选提醒，不自动加入监控。",
        },
        {
            "key": "indicator_cross_alert",
            "name": "指标交叉提醒",
            "status": "partial_legacy",
            "description": "MACD/KDJ gate 和模板存在，但当前没有 active scheduler 直接触发。",
        },
    ],
    "factor_groups": [
        {
            "key": "top_rise_entry",
            "name": "布林贴顶加速上涨模型入场因子",
            "model": "model_top_rise",
            "factors": [
                {
                    "id": "A",
                    "key": "no_bearish_4h_guard",
                    "name": "4小时风险过滤通过",
                    "description": "4小时价格没有明显远离布林上轨等过热风险。",
                },
                {
                    "id": "B",
                    "key": "1d_ema_bullish_stack",
                    "name": "日线 EMA 多头",
                    "description": "日线 EMA12 大于 EMA26。",
                },
                {
                    "id": "C",
                    "key": "4h_bullish_k_ratio",
                    "name": "4小时阳线比例",
                    "description": "4小时最近窗口内阳线比例达到策略要求。",
                },
                {
                    "id": "D",
                    "key": "4h_close_above_ema12",
                    "name": "4小时收盘站上 EMA12",
                    "description": "4小时连续 K 线收盘价位于 EMA12 上方。",
                },
                {
                    "id": "E",
                    "key": "4h_boll_upper_widen",
                    "name": "4小时贴近上轨且开口扩大",
                    "description": "4小时贴近布林上轨，同时布林带开口扩大。",
                },
                {
                    "id": "F",
                    "key": "1h_bullish_k_3",
                    "name": "1小时连续阳线",
                    "description": "1小时最近 3 根 K 线均为阳线。",
                },
                {
                    "id": "G",
                    "key": "1h_along_upper_band",
                    "name": "1小时沿布林上轨",
                    "description": "1小时 K 线沿布林上轨运行。",
                },
            ],
        },
        {
            "key": "top_rise_twice_entry",
            "name": "布林贴顶二次入场因子",
            "model": "model_top_rise:twice",
            "factors": [
                {
                    "id": "H",
                    "key": "4h_new_high_after_range",
                    "name": "4小时盘整后突破新高",
                    "description": "当前价格突破 4小时近 20 根前高，且近期出现过贴近上轨。",
                },
                {
                    "id": "I",
                    "key": "1h_volume_breakout",
                    "name": "1小时放量突破",
                    "description": "1小时当前或前一根成交量高于近 10 根均量 1.5 倍。",
                },
                {
                    "id": "J",
                    "key": "1h_macd_continue_up",
                    "name": "1小时 MACD 柱体放大",
                    "description": "1小时 MACD 连续增强，并伴随放量确认。",
                },
                {
                    "id": "K",
                    "key": "1h_rsi_breakout",
                    "name": "1小时 RSI 突破",
                    "description": "1小时 RSI 高于 70 且继续突破。",
                },
            ],
        },
        {
            "key": "oscillation_state",
            "name": "4小时震荡状态因子",
            "model": "model_oscillation",
            "factors": [
                {
                    "id": "L",
                    "key": "4h_mixed_candles",
                    "name": "4小时 K 线混乱",
                    "description": "4小时出现多根长影线、十字线或方向混乱 K 线。",
                },
                {
                    "id": "M",
                    "key": "4h_near_boll_mid",
                    "name": "4小时贴近布林中轨",
                    "description": "4小时价格多次靠近布林中轨。",
                },
                {
                    "id": "N",
                    "key": "4h_macd_near_zero",
                    "name": "4小时 MACD 接近零轴",
                    "description": "4小时 MACD 柱体缩短并接近零轴。",
                },
                {
                    "id": "O",
                    "key": "4h_rsi_neutral",
                    "name": "4小时 RSI 中性",
                    "description": "4小时 RSI 维持在 30 到 70 的中性区间。",
                },
            ],
        },
        {
            "key": "top_rise_exit",
            "name": "布林贴顶加速上涨模型出场因子",
            "model": "model_top_rise",
            "factors": [
                {
                    "id": "P",
                    "key": "4h_macd_continue_down",
                    "name": "4小时 MACD 动能衰减",
                    "description": "4小时 MACD 柱体连续缩短。",
                },
                {
                    "id": "Q",
                    "key": "4h_kdj_death_cross",
                    "name": "4小时 KDJ 死叉下行",
                    "description": "4小时 KDJ 死叉且 J 值继续下行。",
                },
                {
                    "id": "R",
                    "key": "4h_rsi_fast_down",
                    "name": "4小时 RSI 快速回落",
                    "description": "4小时 RSI 快速跌破高位阈值。",
                },
                {
                    "id": "S",
                    "key": "4h_bearish_price_action",
                    "name": "4小时看跌价格行为",
                    "description": "4小时出现看跌吞没、远离上轨后回落或 KDJ 出场死叉。",
                },
            ],
        },
    ],
    "strategies": [
        {
            "key": "model_top_rise",
            "name": "布林贴顶加速上涨模型",
            "status": "live_entry_and_exit",
            "entry_expression": "A+B+C+D+E+(F|G)",
            "entry_examples": ["A+B+C+D+E+F", "A+B+C+D+E+G"],
            "exit_expression": "any 2 of P+Q+R, then S",
            "source": "models/strategy.py::ModelTopRise",
            "admin_display": {
                "summary": "趋势追踪模型：大周期多头，4小时贴上轨加速，1小时继续确认。",
                "show_factor_ids": True,
            },
        },
        {
            "key": "model_top_rise:twice",
            "name": "布林贴顶二次入场",
            "status": "live_entry_variant",
            "entry_expression": "A+H+(I|J|K)",
            "entry_examples": ["A+H+I", "A+H+J", "A+H+K"],
            "source": "models/strategy.py::ModelTopRise.is_in_twice",
            "admin_display": {
                "summary": "强势趋势中盘整后再次突破，用放量、MACD 或 RSI 做确认。",
                "show_factor_ids": True,
            },
        },
        {
            "key": "model_oscillation",
            "name": "4小时震荡模型",
            "status": "live_state_marker",
            "entry_expression": "any 2 of L+M+N+O",
            "entry_examples": ["L+M", "L+N", "M+O"],
            "source": "models/strategy.py::ModelOscillation",
            "admin_display": {
                "summary": "更像市场状态标签，目前没有 is_buy=True，不应直接展示为正式买入信号。",
                "show_factor_ids": True,
            },
        },
        {
            "key": "multi_factor_score",
            "name": "多因子打分",
            "status": "available_not_live_trigger",
            "entry_expression": "score factors, no current live threshold trigger",
            "entry_examples": ["4h_has_ema_stack+kdj_4h+rsi_1h", "boll_1h+vol_4h_continue_up+fng_lt_20"],
            "source": "business/strategy.py::get_buy_by_multi_factor_score_info",
            "admin_display": {
                "summary": "当前可用于展示分数和因子贡献，但 live 入场触发逻辑仍是注释状态。",
                "show_factor_ids": False,
            },
        },
    ],
    "record_status_text": SIGNAL_RECORD_STATUS_TEXT,
}


def get_signal_catalog():
    return SIGNAL_CATALOG
