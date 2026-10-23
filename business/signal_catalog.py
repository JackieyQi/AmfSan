#! /usr/bin/env python
# coding:utf8
"""Read-only catalog exported from executable strategy definitions."""
from models.strategy_rules import get_strategy_definitions


SIGNAL_RECORD_STATUS_TEXT = {
    0: "入场信号待确认",
    1: "入场信号已记录，等待出场信号",
    2: "入场信号失效",
    3: "出场信号待确认",
    4: "出场信号已记录",
    5: "出场信号按当前价记录",
}



def get_signal_catalog():
    catalog = get_strategy_definitions()
    for key, name in [
        ("model_top_rise:twice", "布林贴顶二次入场"),
        ("model_oscillation", "4小时震荡模型"),
        ("model_boll_mid_rebound", "强趋势布林中轨反弹"),
        ("model_boll_low_rebound_bullish_sideways", "多头震荡布林下轨反弹"),
        ("model_boll_low_rebound_bullish_Down", "多头下跌布林下轨反弹"),
        ("model_l_type_rebound", "L 形反弹"),
        ("model_w_type_rebound", "W 形反弹"),
        ("model_v_type_rebound", "V 形反弹"),
        ("multi_factor_score", "多因子评分流程"),
    ]:
        catalog["models"].append({
            "key": key, "name": name, "version": "legacy",
            "status": "待整理 · 未启用 · 只读",
            "summary": "保留原有实现，尚未迁移为可配置条件组合，当前监控不使用。",
            "entry": None, "exit": None,
        })
    catalog.update({
        "schema_version": "2026-10-21",
        "record_status_text": SIGNAL_RECORD_STATUS_TEXT,
        "notes": [
            "当前监控固定使用布林贴顶加速上涨模型，按用户选择的方向判断并通知。",
            "策略通知不自动生成模拟交易记录；止盈止损价格提醒独立运行。",
            "二次入场、震荡模型和多因子打分尚未接入当前监控，不列为启用策略。",
            "规则保留现有未收盘 K 线用法。页面展示的是规则定义，不是当前行情的判断结果。",
        ],
    })
    return catalog
