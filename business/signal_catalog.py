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
