#! /usr/bin/env python
# -*- coding: UTF-8 -*-

import numpy as np
import pandas as pd
from utils.common import str2decimal


def analyze_list_trend(decimal_array, num=8):
    """
    基于最小二乘多项式拟合，使用线性回归计算趋势
    """
    float_array = np.array([float(i) for i in decimal_array])

    # 计算相邻元素的差值
    differences = np.diff(float_array)

    # 计算基本统计量
    trend_stats = {
        "total_change": float_array[-1] - float_array[0],    # 总体变化量
        "mean_rate": np.mean(differences),    # 平均变化率
        "up_count": np.sum(differences > 0),    # 增长次数
        "down_count": np.sum(differences < 0),    # 下降次数
        # "max_diff": np.max(differences),    # 最大增长
        # "min_diff": np.min(differences),    # 最大下降
        "variance": np.var(differences),    # 方差
    }

    # 使用线性回归计算趋势, 最小二乘多项式拟合
    x = np.arange(len(float_array))
    slope, *args = np.polyfit(x, float_array, 1)
    slope = str2decimal(slope, num)

    # TODO: 根据slope和macd小数位，调整判断值
    if slope > 0 and trend_stats["up_count"] >= trend_stats["down_count"]:
        # trend = "明显上升趋势"
        trend = "parabolic_move"
    elif slope < 0 and trend_stats["down_count"] >= trend_stats["up_count"]:
        # trend = "明显下降趋势"
        trend = "downward_spiral"
    elif trend_stats["total_change"] > 0:
        # trend = "轻微上升趋势"
        trend = "modest_increase"
    elif trend_stats["total_change"] < 0:
        # trend = "轻微下降趋势"
        trend = "modest_decline"
    else:
        # trend = "无明显趋势"
        trend = "range_bound"
    return trend, trend_stats


def calculate_bollinger_bands(close_prices_array, ema_array, std_multiplier=2, ema_window=26):
    """
    基于EMA，计算布林线指标(BOLL指标)
    :param close_prices_array:
    :param ema_array:
    :param std_multiplier: 标准查倍数, 通常为2
    :param ema_window: EMA窗口值
    :return:
    """
    close_prices_array = np.array([float(i) for i in close_prices_array])
    ema_array = np.array([float(i) for i in ema_array])

    df = pd.DataFrame({"ema": ema_array, "close": close_prices_array})
    rolling_std = df["close"].ewm(ema_window, adjust=False).std()

    # 布林带上轨
    higher_band = df["ema"] + (rolling_std * std_multiplier)
    last_higher_band = higher_band.tail(1).values[0]

    # 布林带下轨
    lower_band = df["ema"] - (rolling_std * std_multiplier)
    last_lower_band = lower_band.tail(1).values[0]
    return str2decimal(last_higher_band), str2decimal(last_lower_band)


def calculate_cv(decimal_array, num=1):
    """
    计算离散程度，变异系数=标准差/平均值
    """
    standard_deviation = np.std(decimal_array)
    mean = np.average(decimal_array)
    if not mean or mean <= 0:
        return

    cv = standard_deviation/mean
    return str2decimal(cv, num)
