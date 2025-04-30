#! /usr/bin/env python
# -*- coding: UTF-8 -*-

from decimal import Decimal
from utils.common import autoscale
from utils.indicators import analyze_list_trend, enhanced_analyze_list_trend_by_groups, calculate_cv, analyze_crossovers


class CandlestickFactor:
    def __init__(self, kline_list, macd_list, bb_list):
        # 时间倒序
        self.kline_list = kline_list
        self.macd_list = macd_list
        self.bb_list = bb_list

    def get_donchian_channel(self, window_size=6):
        """
        突破策略: 唐奇安通道策略（Donchian Channel）:
            价格突破过去 20 天最高价，买入
            价格跌破过去 20 天最低价，卖出
        """
        high_list, low_list = [], []
        for i in self.kline_list[1:window_size+1]:
            high_list.append(i.high_price)
            low_list.append(i.low_price)
        return {"max_price": max(high_list), "min_price": min(low_list)}

    def is_new_low_price(self, window_size):
        return self.kline_list[0].low_price < self.get_donchian_channel(window_size)["min_price"]

    def is_new_high_price(self, window_size):
        return self.kline_list[0].high_price < self.get_donchian_channel(window_size)["max_price"]

    def is_bullish_k(self, index=0):
        return self.kline_list[index].open_price < self.kline_list[index].close_price

    def is_bearish_k(self, index=0):
        return self.kline_list[index].open_price > self.kline_list[index].close_price

    def is_bullish_engulfing_k(self, index=0):
        """
        看涨吞没：当前 K 线阳线，实体部分完全包住前一根阴线 → 买入信号
        """
        return (self.kline_list[index+1].open_price > self.kline_list[index+1].close_price) \
            and (self.kline_list[index].open_price < self.kline_list[index].close_price) \
            and (self.kline_list[index].open_price <= self.kline_list[index+1].close_price) \
            and (self.kline_list[index].close_price > self.kline_list[index+1].open_price)

    def get_engulfing_pattern_factor(self, window_index=0):
        """
        形态策略: 吞没形态（Engulfing Pattern）:
            看涨吞没：当前 K 线阳线，实体部分完全包住前一根阴线 → 买入信号
            看跌吞没：当前 K 线阴线，实体部分完全包住前一根阳线 → 卖出信号
        :return:
        """
        curr_index = window_index
        last_index = window_index + 1
        has_bullish_engulfing, has_bearish_engulfing = False, False

        if (self.kline_list[last_index].open_price > self.kline_list[last_index].close_price) \
                and (self.kline_list[curr_index].open_price < self.kline_list[curr_index].close_price) \
                and (self.kline_list[curr_index].open_price < self.kline_list[last_index].close_price) \
                and (self.kline_list[curr_index].close_price > self.kline_list[last_index].open_price):
            has_bullish_engulfing = True

        if (self.kline_list[last_index].open_price < self.kline_list[last_index].close_price) \
                and (self.kline_list[curr_index].open_price > self.kline_list[curr_index].close_price) \
                and (self.kline_list[curr_index].open_price > self.kline_list[last_index].close_price) \
                and (self.kline_list[curr_index].close_price < self.kline_list[last_index].open_price):
            has_bearish_engulfing = True
        return {"has_bullish_engulfing": has_bullish_engulfing, "has_bearish_engulfing": has_bearish_engulfing}

    def get_long_upper_shadow(self, index=0, scale=Decimal("1.5")):
        """
        长上影线可能是诱多 -> -2 分
        """
        real_body = abs(self.kline_list[index].close_price - self.kline_list[index].open_price)
        upper_shadow_body = self.kline_list[index].high_price - max(
            self.kline_list[index].open_price, self.kline_list[index].close_price)

        return upper_shadow_body > real_body * scale

    def get_crosshairs(self, index=0, scale=Decimal("0.15")):
        """ 长十字线"""
        real_body = abs(self.kline_list[index].close_price - self.kline_list[index].open_price)
        range_total_body = self.kline_list[index].high_price - self.kline_list[index].low_price

        return real_body < range_total_body * scale

    def is_long_lower_shadow_k(self, index=0, scale=Decimal("1.5")):
        """
        长下影线可能是诱空 -> +2 分
        :return:
        """
        real_body = abs(self.kline_list[index].close_price - self.kline_list[index].open_price)
        lower_shadow_body = min(self.kline_list[index].open_price, self.kline_list[index].close_price
                                ) - self.kline_list[index].low_price
        return lower_shadow_body > real_body * scale

    def get_corsshairs_and_long_lower_shadow(self, index=0):
        """
        判断：长十字线 + 下影线更长 -> -3 分
        """
        is_crosshairs = self.get_crosshairs(index)

        upper_shadow_body = self.kline_list[index].high_price - max(
            self.kline_list[index].open_price, self.kline_list[index].close_price)
        lower_shadow_body = min(self.kline_list[index].open_price, self.kline_list[index].close_price
                                ) - self.kline_list[index].low_price
        range_total_body = self.kline_list[index].high_price - self.kline_list[index].low_price
        return is_crosshairs and (lower_shadow_body > upper_shadow_body*Decimal("1.2")) and (
            lower_shadow_body > range_total_body*Decimal("0.3")
        )

    def has_double_top(self, total_size=10, window_size=1):
        """
        是否双顶形态
        :return:
        """
        first_peak_price = 0
        second_peak_price = 0
        for i in range(window_size, total_size-window_size):
            left = self.kline_list[i-window_size: i]
            left_prices = [v.high_price for v in left]

            right = self.kline_list[i+1: i+window_size+1]
            right_prices = [v.high_price for v in right]

            if self.kline_list[i].high_price > max(left_prices) and self.kline_list[i].high_price > max(right_prices):
                if not first_peak_price:
                    first_peak_price = self.kline_list[i].high_price
                if not second_peak_price:
                    second_peak_price = self.kline_list[i].high_price
                break

        if first_peak_price and second_peak_price and (first_peak_price < second_peak_price):
            return True
        else:
            return False

    def is_breakdown_by_bb(self, window_size=7, is_low=True):
        if is_low:
            prices_dict = {i.open_ts: i.bblower for i in self.bb_list[:window_size-1]}
        else:
            prices_dict = {i.open_ts: i.bbmid for i in self.bb_list[:window_size-1]}

        for i in self.kline_list[:window_size-1]:
            if i.open_ts in prices_dict and i.close_price < prices_dict[i.open_ts]:
                return True
        return False

    def get_fake_breakout_by_bb(self, index=0, is_up=True):
        """
        k线的假突破
        """
        break_line = self.bb_list[index].bbupper if is_up else self.bb_list[index].bbmid
        if (self.kline_list[index].high_price > break_line) \
                and (self.kline_list[index].close_price < break_line):
            return True
        else:
            return False

    def get_fake_breakdown_by_bb(self, index=0, is_low=True):
        """
        k线的假跌破
        """
        if is_low:
            break_line = self.bb_list[index].bblower
            is_near = self.is_near_lower(index=index, tolerance=Decimal("0.13"))
        else:
            break_line = self.bb_list[index].bbmid
            is_near = self.is_near_mid(index=index)

        if (self.kline_list[index].low_price < break_line) \
                and ((self.kline_list[index].close_price > break_line) or is_near):
            return True
        else:
            return False

    def get_first_breakout_by_bb(self, index=0):
        """
        首次冲高 + 上轨附近
        """

        if self.kline_list[index].close_price < self.bb_list[index].bbmid:
            return False

        if self.kline_list[index+1].low_price < self.bb_list[index+1].bbupper < self.kline_list[index+1].high_price:
            return False

        trend_str, _ = analyze_list_trend([i.high_price for i in self.kline_list[index:index+3]][::-1])
        if trend_str != "parabolic_move":
            return False

        if self.is_near_upper(index, tolerance=Decimal("0.2")):
            return True
        else:
            return False

    def is_near_upper(self, index=0, tolerance=Decimal("0.1")):
        """
        当前价格接近或突破布林带上轨

            if ratio <= 0.05:
                score += 5  # 极贴轨
            elif ratio <= 0.15:
                score += 3  # 贴轨
            elif ratio <= 0.3:
                score += 1  # 靠近但不强
        """
        if self.kline_list[index].close_price < self.bb_list[index].bbmid:
            return False

        band_width = self.bb_list[index].bbupper - self.bb_list[index].bbmid
        return (self.bb_list[index].bbupper - self.kline_list[index].close_price) / band_width <= tolerance

    def is_near_mid(self, index=0, tolerance=Decimal("0.02")):
        """
        当前价格接近或突破布林带中轨
        """
        if self.kline_list[index].close_price < self.bb_list[index].bblower:
            return False

        band_width = self.bb_list[index].bbupper - self.bb_list[index].bbmid
        return abs(self.kline_list[index].close_price - self.bb_list[index].bbmid) / band_width <= tolerance

    def is_near_lower(self, index=0, tolerance=Decimal("0.1")):
        """
        当前价格接近或突破布林带下轨
        """
        if self.kline_list[index].close_price > self.bb_list[index].bbmid:
            return False

        band_width = self.bb_list[index].bbmid - self.bb_list[index].bblower
        return abs(self.kline_list[index].close_price - self.bb_list[index].bblower) / band_width <= tolerance

    def is_along_upper_band(self, n=5, tolerance=Decimal("0.2")):
        """
        判断是否沿着上轨运行
        :param tolerance: 容差范围，比如 0.02 表示距离上轨在 2% 以内算“贴近”
        """
        count = 0
        for i in range(n-1, -1, -1):
            if self.kline_list[i].close_price < self.bb_list[i].bbmid:
                continue

            if (self.bb_list[i].bbupper - self.kline_list[i].close_price) / (
                    self.bb_list[i].bbupper - self.bb_list[i].bbmid) <= tolerance:
                count += 1
        return count > n * 0.5  # 至少70%贴近上轨

    def is_along_lower_band(self, n=3, tolerance=Decimal("0.02")):
        """
        判断是否沿着下轨轨运行
        :param tolerance: 容差范围，比如 0.02 表示距离上轨在 2% 以内算“贴近”
        """
        count = 0
        for i in range(n-1, -1, -1):
            if self.kline_list[i].close_price > self.bb_list[i].bbmid:
                continue

            if (self.kline_list[i].close_price - self.bb_list[i].bblower) / (
                    self.bb_list[i].bbmid - self.bb_list[i].bblower) <= tolerance:
                count += 1
            elif self.kline_list[i].low_price < self.bb_list[i].bblower:
                count += 1
        return count > n * 0.7  # 至少70%贴近上轨

    def get_boll_bandwidth_trend(self, window_size=24):
        bandwidth_list = [i.bbupper - i.bblower for i in self.bb_list[:window_size-1]][::-1]
        return enhanced_analyze_list_trend_by_groups(bandwidth_list)

    def get_ema_factor(self, is_bid=False, is_ask=False):
        """
        bullish stack（多头叠加、多头堆叠）
            eg: EMA12 > EMA26 > EMA50

        1. 双均线策略（Golden Cross & Death Cross）:
            *计算 短期均线（如 5 日均线）和 长期均线（如 20 日均线）
                短期均线上穿长期均线，买入（金叉）
                短期均线下穿长期均线，卖出（死叉）
        2. 均线上升趋势策略:
            * 短周期均线递增（趋势确认）
            * 均线多头排列（短期均线在上，长期均线在下）
            * 当前价格位于均线区间内（防止价格过高）
        3. 均线上升趋势策略:
            * 最低价跌破短周期均线（趋势转空）
        """
        factors = {}
        curr_price = self.macd_list[0].closing_price

        if is_bid is True:
            if (self.macd_list[0].ema_12 >= self.macd_list[0].ema_26) \
                    and (self.macd_list[1].ema_12 < self.macd_list[1].ema_26):
                factors["has_ema_golden_cross"] = True

            if self.macd_list[0].ema_12 >= self.macd_list[1].ema_12:
                factors["has_ema_uptrend"] = True
            if self.macd_list[0].ema_12 >= self.macd_list[0].ema_26:
                factors["has_ema_stack"] = True
            if self.macd_list[0].ema_12 >= curr_price > self.macd_list[0].ema_26:
                factors["has_nice_price"] = True

            return factors

        if is_ask is True:
            if (self.macd_list[0].ema_12 <= self.macd_list[0].ema_26) \
                    and (self.macd_list[1].ema_12 > self.macd_list[1].ema_26):
                factors["has_death_cross"] = True

            if self.kline_list[0].open_ts == self.macd_list[0].opening_ts:
                if self.kline_list[0].low_price <= min(self.macd_list[0].ema_12, self.macd_list[0].ema_26):
                    factors["has_break_price"] = True

            return factors
        return factors

    def has_ema_bullish_alignment(self, index=0):
        """
        EMA多头排列
        """
        return self.macd_list[index].ema_12 >= self.macd_list[index].ema_26

    def get_prev_ema_trend_factor(self, group_size=7):
        """
        增强版EMA趋势分析，结合历史趋势进行相对判断
        """
        trend_info = enhanced_analyze_list_trend_by_groups(
            [i.ema_12 for i in self.macd_list[1:19]][::-1], group_size=group_size)
        return trend_info

    def get_ema_trend(self, window_size=7):
        trend_list = []
        for i in self.macd_list[:window_size-1][::-1]:
            trend_list.append(i.ema_12 - i.ema_26)

        diff_prices, _ = autoscale(trend_list)
        trend, trend_stats = analyze_list_trend(diff_prices)
        return trend_stats

    def is_ema_bullish_stack(self, window_size=7):
        return all((self.macd_list[i].ema_12 - self.macd_list[i].ema_26) > 0 for i in range(window_size-1))

    def is_ema12_continue_down(self, window_size=7):
        return all(self.macd_list[i].ema_12 > self.macd_list[i - 1].ema_12 for i in range(1, window_size))

    def is_ema12_continue_up(self, window_size=7):
        return all(self.macd_list[i].ema_12 < self.macd_list[i - 1].ema_12 for i in range(1, window_size))

    def is_ema26_continue_up(self, window_size=7):
        return all(self.macd_list[i].ema_26 < self.macd_list[i - 1].ema_26 for i in range(1, window_size))

    def get_vol_factor(self, window_size, rate_threshold=Decimal("1.3")):
        """
        交易量策略:
            短期趋势 → 5~10 天的成交量均线，举例：
                1小时成交量 **高于过去10根均值**，资金流入，增强信号。
                4小时成交量 **高于过去3根均值**，资金持续流入，增强信号。
        :return:
        """
        factors = {"curr_high_price": self.kline_list[0].high_price, }
        curr_volume = self.kline_list[0].volume

        volume_list = []
        high_price_list = []
        for i in self.kline_list[1:window_size+1]:
            volume_list.append(i.volume)
            high_price_list.append(i.high_price)

        if not volume_list:
            return factors
        if high_price_list:
            factors["prev_high_price"] = max(high_price_list)

        last_mean_volume = sum(volume_list) / Decimal(len(volume_list))

        if curr_volume > last_mean_volume:
            factors["has_spike_volume"] = True

        if curr_volume > last_mean_volume * rate_threshold:
            factors["has_enhance_spike_volume"] = True
        return factors


class MacdFactor:
    def __init__(self, macd_list):
        # 时间倒序
        self.macd_list = macd_list

    def get_curr_golden_cross(self):
        """
        macd滞后性强，短线交易中不考虑死叉
        """
        return self.macd_list[0].macd >= 0 and self.macd_list[1].macd < 0

    def get_bullish_stack(self):
        """
        多头排列
        """
        return all(i.macd >= 0 for i in self.macd_list)

    def get_bearish_stack(self):
        """
        空头排列
        """
        return all(i.macd < 0 for i in self.macd_list)

    def get_downtrend(self):
        """
        更大周期趋势->增强短线交易的离场信号
        """
        return self.macd_list[0].macd < self.macd_list[1].macd < self.macd_list[2].macd

    def get_dif_downtrend(self):
        dif = self.macd_list[0].ema_12 - self.macd_list[0].ema_26
        prev_dif = self.macd_list[1].ema_12 - self.macd_list[1].ema_26
        return prev_dif > dif

    def get_prev_trend_factor(self, group_size=7):
        """
        增强版趋势分析，结合历史趋势进行相对判断
        """
        trend_info = enhanced_analyze_list_trend_by_groups(
            [i.macd for i in self.macd_list[1:19]][::-1], group_size=group_size)
        return trend_info

    def get_trend_factor(self):
        """
        趋势分析，基于最小二乘多项式拟合，使用线性回归计算趋势
        """
        trend_str, _ = analyze_list_trend([i.macd for i in self.macd_list[:7]][::-1])
        return {"trend": trend_str, }

    def is_continue_down(self, window_size=3):
        """ macd连续下跌 """
        return all(self.macd_list[i].macd > self.macd_list[i - 1].macd for i in range(1, window_size))


class KdjFactor:
    def __init__(self, kdj_list):
        # 时间倒序
        self.kdj_list = kdj_list

    def get_uptrend(self, window_size):
        """检查KDJ是否处于递增趋势(基于每一组数据的离散值->离散值的数组)"""
        kdj_list = self.kdj_list[:window_size][::-1]

        for i in range(1, len(kdj_list)):
            curr_kdj = kdj_list[i]
            last_kdj = kdj_list[i-1]

            curr_cv = calculate_cv([curr_kdj.k_val, curr_kdj.d_val, curr_kdj.j_val], num=8)
            last_cv = calculate_cv([last_kdj.k_val, last_kdj.d_val, last_kdj.j_val], num=8)
            if (last_kdj.k_val >= last_kdj.d_val) and (curr_kdj.k_val >= curr_kdj.d_val) and (curr_cv <= last_cv):
                return False
            elif (last_kdj.k_val <= last_kdj.d_val) and (curr_kdj.k_val <= curr_kdj.d_val) and (curr_cv > last_cv):
                return False
            elif (last_kdj.k_val >= last_kdj.d_val) and (curr_kdj.k_val <= curr_kdj.d_val):
                return False
        return True

    def get_downtrend(self, window_size):
        """检查KDJ是否处于递减趋势(基于每一组数据的离散值->离散值的数组)"""
        kdj_list = self.kdj_list[:window_size][::-1]

        for i in range(1, len(kdj_list)):
            curr_kdj = kdj_list[i]
            last_kdj = kdj_list[i-1]

            curr_cv = calculate_cv([curr_kdj.k_val, curr_kdj.d_val, curr_kdj.j_val], num=8)
            last_cv = calculate_cv([last_kdj.k_val, last_kdj.d_val, last_kdj.j_val], num=8)
            if (last_kdj.k_val >= last_kdj.d_val) and (curr_kdj.k_val >= curr_kdj.d_val) and (curr_cv > last_cv):
                return False
            elif (last_kdj.k_val <= last_kdj.d_val) and (curr_kdj.k_val <= curr_kdj.d_val) and (curr_cv <= last_cv):
                return False
            elif (last_kdj.k_val <= last_kdj.d_val) and (curr_kdj.k_val >= curr_kdj.d_val):
                return False
        return True

    def get_extreme_increase(self, window_size):
        """检查连续递增，极端超买"""
        return all([i.j_val >= Decimal("100") for i in self.kdj_list[:window_size]])

    def get_history_golden_cross_count(self, window_size, threshold=0):
        """检查 KDJ历史金叉数量"""
        crossovers_data = analyze_crossovers(self.kdj_list[1:window_size])
        return crossovers_data["golden_cross"] > threshold

    def get_sideways(self, window_size=4):
        """检查 KDJ是否震荡"""
        crossovers_data = analyze_crossovers(self.kdj_list[:window_size])
        return crossovers_data["golden_cross"] and crossovers_data["death_cross"]

    def get_curr_golden_cross(self):
        """检查 KDJ当前金叉"""
        return (self.kdj_list[1].k_val < self.kdj_list[1].d_val and
                self.kdj_list[0].k_val > self.kdj_list[0].d_val)

    def get_curr_death_cross(self):
        """检查 KDJ当前死叉"""
        return (self.kdj_list[1].k_val > self.kdj_list[1].d_val and
                self.kdj_list[0].k_val < self.kdj_list[0].d_val)

    def get_curr_golden_cross_by_threshold(self, threshold):
        """检查 KDJ当前低位金叉"""
        return (self.kdj_list[1].k_val <= threshold and
                self.kdj_list[1].d_val <= threshold and
                self.kdj_list[1].j_val <= threshold and
                self.kdj_list[1].k_val < self.kdj_list[1].d_val and
                self.kdj_list[0].k_val > self.kdj_list[0].d_val)

    def get_curr_death_cross_by_threshold(self, threshold):
        """检查 KDJ当前(或者最近)高位死叉"""
        current = (self.kdj_list[1].k_val >= threshold and
                   self.kdj_list[1].d_val >= threshold and
                   self.kdj_list[1].j_val >= threshold and
                   self.kdj_list[1].k_val > self.kdj_list[1].d_val and
                   self.kdj_list[0].k_val < self.kdj_list[0].d_val)

        last = (self.kdj_list[2].k_val >= threshold and
                self.kdj_list[2].d_val >= threshold and
                self.kdj_list[2].j_val >= threshold and
                self.kdj_list[2].k_val > self.kdj_list[2].d_val and
                self.kdj_list[0].k_val < self.kdj_list[0].d_val)
        return current or last

    def is_j_bullish_divergence(self, is_new_low_price, index=0, j_threshold=Decimal("20")):
        """ KDJ极端空头+J值底部背离(价格创新低，J 没创新低) """
        k = self.kdj_list[index].k_val
        d = self.kdj_list[index].d_val
        j = self.kdj_list[index].j_val

        if k < d and (k-j) >= 2*(d-k):
            if is_new_low_price and self.kdj_list[index+1].j_val <= j < j_threshold:
                return True
        return False


class RsiFactor:
    def __init__(self, rsi_list):
        self.rsi_list = rsi_list

    def get_curr_normalize_score(self):
        """归一化到[-1, 1]"""
        return Decimal("2") * (self.rsi_list[0].rsi - Decimal("50")) / Decimal("100")

    def get_pullback_entry(self, breakthrough=Decimal("65"), pullback=Decimal("60")):
        """
        1小时 RSI-6 突破 65 后回踩 60，视为回调进场点（多单）-> +3 分
        跌破 40 后回踩 45，视为回调做空点（空单）
        """
        rsi_array = [i.rsi for i in self.rsi_list[:7]]
        if (rsi_array[0] < pullback) and \
                (max(rsi_array) > breakthrough) and (rsi_array[-1] < Decimal("55")):
            return True
        return False

    def get_uptrend(self):
        """
        1小时 RSI-6 连续3根线递增 -> +5 分
        4 小时 RSI-6 连续 3 根 K 线递增 → +3 分
        """
        return self.rsi_list[0].rsi > self.rsi_list[1].rsi > self.rsi_list[2].rsi

    def get_rebound(self, threshold=Decimal("40")):
        """
        1 小时 RSI-6 低于 40（短期超卖）且反弹 → +5 分。
        """
        return (self.rsi_list[0].rsi > self.rsi_list[1].rsi) \
               and (self.rsi_list[1].rsi < threshold) and (self.rsi_list[1].rsi < self.rsi_list[2].rsi)

    def get_breakout_from_low(self, index=0):
        """
        1小时RSI-6从低位突破50 -> +5 分。
        """
        return self.get_breakout(index=index, threshold=Decimal("50")) \
                and min([i.rsi for i in self.rsi_list[index:5+index]]) < Decimal(40)

    def get_healthy_bound(self):
        """
        1 小时波动过大，不做参考。
        4 小时 RSI-6 在 45-65（中期健康区间） → +3 分。
        """
        return Decimal("45") < self.rsi_list[0].rsi < Decimal("65")

    def get_breakout(self, index=0, threshold=Decimal("60")):
        """
        4 小时 RSI-6 突破 60，增强趋势信号 → +3 分。
        """
        return self.rsi_list[index].rsi > threshold > self.rsi_list[index+1].rsi
