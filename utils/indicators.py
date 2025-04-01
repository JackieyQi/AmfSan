#! /usr/bin/env python
# -*- coding: UTF-8 -*-

import time
import numpy as np
import pandas as pd
from decimal import Decimal
from utils.common import str2decimal, leading_zeros
from cache import AllCache


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
        epsilon = max(str2decimal(epsilon), Decimal("0.00000001"))

        # 计算当前斜率与历史斜率的相对值
        relative_slope = (slope - avg_historical_slope) / max(std_historical_slope, epsilon)

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

    trend_stats["trend"] = trend
    return trend_stats


def enhanced_analyze_list_trend_by_groups(data, group_size=7):
    scale_factor = leading_zeros(data[0])
    if scale_factor:
        for i, val in enumerate(data):
            data[i] = val * scale_factor

    results = []
    for i in range(0, len(data) - group_size + 1):
        group = data[i:i + group_size]

        # 获取之前的趋势数据作为参考
        previous_trends = []
        if i > 0:
            previous_trends = [r["stats"] for r in results]

        stats = enhanced_analyze_list_trend(group, previous_trends)
        results.append({
            "group": i + 1,
            "data": group,
            "stats": stats
        })

    return results[-1]["stats"]


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


def check_near_low(klines_data, support_level, percentage_threshold=0.03, atr_multiplier=0.5, atr_window_size=6):
    """

    :param klines_data: 按时间正序排列
    :param support_level: 支撑位价格
    :param percentage_threshold: 百分比阈值，默认3%
    :param atr_multiplier: ATR倍数阈值，默认0.5倍
    :return:
    """
    df = pd.DataFrame([
        {
            "open": float(k.open_price),
            "high": float(k.high_price),
            "close": float(k.close_price),
            "low": float(k.low_price)
        } for k in klines_data
    ])

    # 获取最新价格数据
    current_low = df["low"].iloc[-1]
    current_close = df["close"].iloc[-1]
    support_level_float = float(support_level)

    # 计算ATR (6周期简化版)
    df["tr"] = np.maximum(
        df["high"] - df["low"],
        np.maximum(
            abs(df['high'] - df['close'].shift(1)),
            abs(df['low'] - df['close'].shift(1))
        )
    )

    # 确保有足够的数据计算ATR
    if len(df) >= atr_window_size:
        atr = df["tr"].rolling(atr_window_size).mean().iloc[-1]
    else:
        atr = df["tr"].mean()  # 如果数据不足14条，使用平均值

    # 计算当前价格与支撑位的距离
    distance = current_low - support_level_float
    percentage_distance = distance / support_level_float
    atr_distance = distance / atr if atr != 0 else float('inf')

    # 判断条件
    is_near_by_percentage = 0 <= percentage_distance <= percentage_threshold
    is_near_by_atr = 0 <= atr_distance <= atr_multiplier
    price_structure_valid = current_low <= support_level_float * (
                1 + percentage_threshold) and current_close > support_level_float

    # 综合判断
    return (is_near_by_percentage or is_near_by_atr) and price_structure_valid


def check_near_high(klines_data, high_level, percentage_threshold=0.03, atr_multiplier=0.5, atr_window_size=6):
    """

    :param klines_data: 按时间正序排列
    :param high_level: 支撑位价格
    :param percentage_threshold: 百分比阈值，默认3%
    :param atr_multiplier: ATR倍数阈值，默认0.5倍
    :return:
    """
    df = pd.DataFrame([
        {
            "open": float(k.open_price),
            "high": float(k.high_price),
            "close": float(k.close_price),
            "low": float(k.low_price)
        } for k in klines_data
    ])

    # 获取最新价格数据
    current_high = df["high"].iloc[-1]
    current_close = df["close"].iloc[-1]
    high_level_float = float(high_level)

    # 计算ATR (6周期简化版)
    df["tr"] = np.maximum(
        df["high"] - df["low"],
        np.maximum(
            abs(df['high'] - df['close'].shift(1)),
            abs(df['low'] - df['close'].shift(1))
        )
    )

    # 确保有足够的数据计算ATR
    if len(df) >= atr_window_size:
        atr = df["tr"].rolling(atr_window_size).mean().iloc[-1]
    else:
        atr = df["tr"].mean()  # 如果数据不足14条，使用平均值

    # 计算当前价格与支撑位的距离
    distance = abs(high_level_float - current_high)
    percentage_distance = distance / high_level_float
    atr_distance = distance / atr if atr != 0 else float('inf')

    # 判断条件
    is_near_by_percentage = 0 <= percentage_distance <= percentage_threshold
    is_near_by_atr = 0 <= atr_distance <= atr_multiplier
    price_structure_valid = current_high >= high_level_float * (
                1 + percentage_threshold) and current_close < high_level_float

    # 综合判断
    return (is_near_by_percentage or is_near_by_atr) and price_structure_valid


def get_atr_price(kline_list, curr_price, window_size=6, tp_threshold=2, sl_threshold=1):
    """
    ATR（真实波动范围）目标价：
        止盈 = 现价 + 2 * ATR(6)
        止损 = 现价 - ATR(6)

    :param kline_list: 时间正序的数组
    :param window_size: 高波动性选择5～6
    :param tp_threshold: 止盈的atr乘数(调整 ATR 乘数（1.5x、2x、2.5x）可适应不同交易风格)
    :param sl_threshold: 止损的atr乘数
    """
    if len(kline_list) != window_size + 1:
        return {}

    sum_tr = Decimal("0")
    for i in range(1, window_size+1):
        high_price = kline_list[i].high_price
        low_price = kline_list[i].low_price
        prev_close_price = kline_list[i-1].close_price

        tr = max(high_price-low_price, abs(high_price-prev_close_price), abs(low_price-prev_close_price))
        sum_tr += tr
    atr = sum_tr / Decimal(window_size)

    tp_price = curr_price + Decimal(tp_threshold) * atr
    sl_price = curr_price - Decimal(sl_threshold) * atr
    return {"tp_price": tp_price, "sl_price": sl_price}


class RollingCounter(object):
    def __init__(self, symbol, counter_name):
        self.symbol = symbol
        self.counter_name = counter_name

        self.redis_client = AllCache.get_client()

    def increment(self):
        ts = int(time.time())

        pipe = self.redis_client.pipeline()
        pipe.zadd(f"{self.counter_name}:{self.symbol}", {str(ts): ts})
        pipe.execute()
        return ts

    def get_last_count(self, interval=86400):
        now = int(time.time())
        time_ago = now - interval

        count = self.redis_client.zcount(
            f"{self.counter_name}:{self.symbol}",
            min=time_ago,
            max=now
        )

        self.redis_client.zremrangebyscore(
            f"{self.counter_name}:{self.symbol}",
            min=0,
            max=time_ago-1
        )
        return count
