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


def enhanced_analyze_list_trend(decimal_array, previous_trends=None, num=8):
    """
    增强版趋势分析，结合历史趋势进行相对判断
    """
    float_array = np.array([float(i) for i in decimal_array])

    # 计算相邻元素的差值
    differences = np.diff(float_array)

    # 计算基本统计量
    trend_stats = {
        "total_change": float_array[-1] - float_array[0],  # 总体变化量
        "mean_rate": np.mean(differences),  # 平均变化率
        "up_count": np.sum(differences > 0),  # 增长次数
        "down_count": np.sum(differences < 0),  # 下降次数
        "variance": np.var(differences),  # 方差
    }

    # 使用线性回归计算趋势
    x = np.arange(len(float_array))
    slope, *args = np.polyfit(x, float_array, 1)
    slope = str2decimal(slope, num)
    trend_stats["slope"] = slope

    # 如果没有历史趋势数据，使用原始判断逻辑
    if previous_trends is None or len(previous_trends) == 0:
        if slope > 0 and trend_stats["up_count"] >= trend_stats["down_count"]:
            trend = "parabolic_move"
        elif slope < 0 and trend_stats["down_count"] >= trend_stats["up_count"]:
            trend = "downward_spiral"
        elif trend_stats["total_change"] > 0:
            trend = "modest_increase"
        elif trend_stats["total_change"] < 0:
            trend = "modest_decline"
        else:
            trend = "range_bound"
    else:
        # 从历史趋势中提取斜率和方差数据
        historical_slopes = [t.get("slope", 0) for t in previous_trends]
        historical_variances = [t.get("variance", 0) for t in previous_trends]
        historical_mean_rates = [t.get("mean_rate", 0) for t in previous_trends]

        # 计算历史斜率的均值和标准差
        avg_historical_slope = np.mean(historical_slopes)
        std_historical_slope = np.std(historical_slopes)

        # 设定安全值，避免分母为负数。
        epsilon = np.mean(abs(float(avg_historical_slope))) * 0.001
        # epsilon = Decimal("0.0001")

        # 计算当前斜率与历史斜率的相对值
        relative_slope = (slope - avg_historical_slope) / max(std_historical_slope, str2decimal(epsilon))

        # 计算历史方差的均值
        avg_historical_variance = np.mean(historical_variances)

        # 计算历史平均变化率的均值和标准差
        avg_historical_mean_rate = np.mean(historical_mean_rates)
        std_historical_mean_rate = np.std(historical_mean_rates)

        # 计算当前平均变化率与历史平均变化率的相对值
        relative_mean_rate = (trend_stats["mean_rate"] - avg_historical_mean_rate) / max(
            std_historical_mean_rate, 0.0001)

        # 相对阈值0.7和0.5是用来判断趋势强度的参考值，其他比如0.5和0.3、0.8和0.6，参考值越大，越需要大波动。
        """
        调整阈值的一般原则：
        数据波动性：高波动数据需要更高阈值，低波动数据可用较低阈值
        后果敏感性：错过重要趋势代价高的场景，使用较低阈值；误报成本高的场景，用较高阈值
        历史表现：分析历史数据，找出"真正的趋势变化"时的相对值，以此设定阈值
        反馈调整：实际应用一段时间后，根据结果准确性来微调阈值

        最佳做法是使用历史数据进行回测，找出能够正确识别您所关心趋势变化的阈值组合，然后在实际应用中继续监控并调整。
        """
        # 基于相对指标判断趋势
        if relative_slope > 0.7 and relative_mean_rate > 0.5 and trend_stats["up_count"] > trend_stats["down_count"]:
            trend = "parabolic_move"
        elif relative_slope < -0.7 and relative_mean_rate < -0.5 and trend_stats["down_count"] > trend_stats[
            "up_count"]:
            trend = "downward_spiral"
        elif slope > 0 and (relative_slope <= 0.7 or relative_mean_rate <= 0.5):
            trend = "modest_increase"
        elif slope < 0 and (relative_slope >= -0.7 or relative_mean_rate >= -0.5):
            trend = "modest_decline"
        else:
            # 如果方差较大或上升/下降次数相等，则判断为无明显趋势
            if trend_stats["variance"] > avg_historical_variance * 1.5 or trend_stats["up_count"] == trend_stats[
                "down_count"]:
                trend = "range_bound"
            elif trend_stats["total_change"] > 0:
                trend = "modest_increase"
            elif trend_stats["total_change"] < 0:
                trend = "modest_decline"
            else:
                trend = "range_bound"

    return trend, trend_stats


def enhanced_analyze_by_groups(data, group_size=7):
    results = []
    for i in range(0, len(data) - group_size + 1):
        group = data[i:i + group_size]

        # 获取之前的趋势数据作为参考
        previous_trends = []
        if i > 0:
            previous_trends = [r["stats"] for r in results]

        trend, stats = enhanced_analyze_list_trend(group, previous_trends)
        results.append({
            "group": i + 1,
            "data": group,
            "trend": trend,
            "stats": stats
        })

    return results[-1]["trend"]


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


def analyze_crossovers(data_array):
    """
    计算数组的交叉比例
    :param data_array: 时间倒序排列的指标数组
    :return:
    """
    if len(data_array) < 2:
        return

    golden_cross = 0  # 金叉计数
    death_cross = 0  # 死叉计数

    for i in range(len(data_array) - 1):
        current = data_array[i]
        next_point = data_array[i + 1]

        if current.k_val <= current.d_val and next_point.k_val > next_point.d_val:
            death_cross += 1
        elif current.k_val >= current.d_val and next_point.k_val < next_point.d_val:
            golden_cross += 1

    total_crosses = golden_cross + death_cross
    if total_crosses > 0:
        golden_ratio = (golden_cross / total_crosses) * 100
        death_ratio = (death_cross / total_crosses) * 100
        golden_ratio_str = f"{golden_ratio:.1f}%"
        death_ratio_str = f"{death_ratio:.1f}%"

    return {
        "total_crosses": total_crosses,
        "golden_cross": golden_cross,
        "death_cross": death_cross,
    }
