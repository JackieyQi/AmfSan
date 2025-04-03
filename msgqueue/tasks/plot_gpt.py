#! /usr/bin/env python
# -*- coding: UTF-8 -*-
"""
🧠
* 1小时线、4小时线和日线的联合判断，能够有效过滤掉单一时间周期的噪声和假信号。
* MACD看趋势，KDJ看转折，MACD的金叉/死叉确认主趋势，而KDJ的超买超卖区间判断买卖点。
* “多周期共振”是关键，仅依赖1小时线或4小时线的信号容易出现误判。

"""

import hashlib
import logging
import time
import json
from decimal import Decimal

from exts import async_database
from cache import AllCache
from cache.order import MarketPriceLimitCache, FearAndGreedIndexCache
from models.market import KlineTable, MacdTable, KdjTable, RsiTable
from models.order import PlotBackTestTable
from models.user import EmailMsgHistoryTable
from settings.constants import PLOT_INTERVAL_CONFIG, INNER_GET_DELETE_LIMIT_PRICE_URL, INNER_GET_SUBMIT_LIMIT_PRICE_URL
from utils.common import ts2bjfmt, str2decimal, decimal2decimal
from utils.hrequest import http_get_request
from utils.indicators import analyze_list_trend, calculate_bollinger_bands, calculate_cv, analyze_crossovers, \
    enhanced_analyze_list_trend_by_groups, RollingCounter, check_near_low, get_atr_price, check_near_high
from utils.templates import template_gpt_plot_trend_following_strategy_notice, \
    template_gpt_plot_short_term_strategy_notice, template_gpt_plot_bull_run_strategy_notice, template_strategy_notice
from business.back_test import BackTestHandler
from .base import BasePlotHandle

logger = logging.getLogger(__name__)


TMP_STAR_TOP10 = ["pnutusdt", "eigenusdt", "wifusdt", "beamxusdt", "dogeusdt", "peopleusdt", "fetusdt", "shibusdt", "opusdt"]


class CandlestickStrategy:
    def __init__(self, kline_list, macd_list):
        # 时间倒序
        self.kline_list = kline_list
        self.macd_list = macd_list

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
        return {"max_price": max(high_list[:window_size]), "min_price": min(low_list[:window_size])}

    def get_engulfing_pattern_strategy(self, window_index=0):
        """
        形态策略: 吞没形态（Engulfing Pattern）:
            看涨吞没：当前 K 线阳线，实体部分完全包住前一根阴线 → 买入信号
            看跌吞没：当前 K 线阴线，实体部分完全包住前一根阳线 → 卖出信号
        :return:
        """
        curr_index = window_index
        last_index = window_index + 1
        has_bullish_engulfing, has_bearish_engulfing = False, False

        if (self.kline_list[curr_index].open_price < self.kline_list[last_index].close_price) \
                and (self.kline_list[curr_index].close_price > self.kline_list[last_index].open_price):
            has_bullish_engulfing = True

        if (self.kline_list[curr_index].open_price >= self.kline_list[last_index].close_price) \
                and (self.kline_list[curr_index].close_price < self.kline_list[last_index].open_price):
            has_bearish_engulfing = True
        return {"has_bullish_engulfing": has_bullish_engulfing, "has_bearish_engulfing": has_bearish_engulfing}

    def get_rsi(self):
        """
        动量策略:
            RSI（相对强弱指数）策略:
                RSI > 70，超买，考虑做空
                RSI < 30，超卖，考虑做多
        """
        pass

    def get_bollinger_bands(self):
        """
        布林带策略：
            买入：价格突破上轨，趋势延续
            卖出：价格跌破下轨，趋势反转
        """

        macd_list = self.macd_list[1:27]
        close_prices = [row.closing_price for row in macd_list]
        ema_values = [row.ema_26 for row in macd_list]

        bb_upper, bb_lower = calculate_bollinger_bands(close_prices[::-1], ema_values[::-1])
        bb_mid = (bb_upper + bb_lower) / Decimal(2)
        return {"bb_upper": bb_upper, "bb_lower": bb_lower, "bb_mid": bb_mid}

    def get_ema_strategy(self, is_bid=False, is_ask=False):
        """
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
        strategies = {}
        curr_price = self.macd_list[0].closing_price

        if is_bid is True:
            if (self.macd_list[0].ema_12 >= self.macd_list[0].ema_26) \
                    and (self.macd_list[1].ema_12 < self.macd_list[1].ema_26):
                strategies["has_ema_golden_cross"] = True

            if self.macd_list[0].ema_12 >= self.macd_list[1].ema_12:
                strategies["has_ema_uptrend"] = True
            if self.macd_list[0].ema_12 >= self.macd_list[0].ema_26:
                strategies["has_ema_stack"] = True
            if self.macd_list[0].ema_12 >= curr_price > self.macd_list[0].ema_26:
                strategies["has_nice_price"] = True

            return strategies

        if is_ask is True:
            if (self.macd_list[0].ema_12 <= self.macd_list[0].ema_26) \
                    and (self.macd_list[1].ema_12 > self.macd_list[1].ema_26):
                strategies["has_death_cross"] = True

            if self.kline_list[0].open_ts == self.macd_list[0].opening_ts:
                if self.kline_list[0].low_price <= min(self.macd_list[0].ema_12, self.macd_list[0].ema_26):
                    strategies["has_break_price"] = True

            return strategies
        return strategies

    def get_prev_ema_trend_strategy(self, group_size=7):
        """
        增强版EMA趋势分析，结合历史趋势进行相对判断
        """
        trend_info = enhanced_analyze_list_trend_by_groups(
            [i.ema_12 for i in self.macd_list[1:19]][::-1], group_size=group_size)
        return trend_info

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

    def get_vol_strategy(self, window_size, rate_threshold=Decimal("1.3")):
        """
        交易量策略:
            短期趋势 → 5~10 天的成交量均线，举例：
                1小时成交量 **高于过去10根均值**，资金流入，增强信号。
                4小时成交量 **高于过去3根均值**，资金持续流入，增强信号。
        :return:
        """
        strategies = {}
        curr_volume = self.kline_list[0].volume

        volume_list = [i.volume for i in self.kline_list[1:window_size+1]]
        last_mean_volume = sum(volume_list) / Decimal(len(volume_list))

        if curr_volume > last_mean_volume:
            strategies["has_spike_volume"] = True

        if curr_volume > last_mean_volume * rate_threshold:
            strategies["has_enhance_spike_volume"] = True
        return strategies


class MacdStrategy:
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
        return self.macd_list[0].macd <= self.macd_list[1].macd

    def get_dif_downtrend(self):
        dif = self.macd_list[0].ema_12 - self.macd_list[0].ema_26
        prev_dif = self.macd_list[1].ema_12 - self.macd_list[1].ema_26
        return prev_dif > dif

    def get_prev_trend_strategy(self, group_size=7):
        """
        增强版趋势分析，结合历史趋势进行相对判断
        """
        trend_info = enhanced_analyze_list_trend_by_groups(
            [i.macd for i in self.macd_list[1:19]][::-1], group_size=group_size)
        return trend_info

    def get_trend_strategy(self):
        """
        趋势分析，基于最小二乘多项式拟合，使用线性回归计算趋势
        """
        trend_str, _ = analyze_list_trend([i.macd for i in self.macd_list[:7]][::-1])
        return {"trend": trend_str, }


class KdjStrategy:
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


class RsiStrategy:
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

    def get_rebound(self):
        """
        1 小时 RSI-6 低于 40（短期超卖）且反弹 → +5 分。
        """
        return (self.rsi_list[0].rsi > self.rsi_list[1].rsi) \
               and (self.rsi_list[1].rsi < Decimal("40")) and (self.rsi_list[1].rsi < self.rsi_list[2].rsi)

    def get_healthy_bound(self):
        """
        1 小时波动过大，不做参考。
        4 小时 RSI-6 在 45-65（中期健康区间） → +3 分。
        """
        return Decimal("45") < self.rsi_list[0].rsi < Decimal("65")

    def get_breakout(self):
        """
        4 小时 RSI-6 突破 60，增强趋势信号 → +3 分。
        """
        return self.rsi_list[0].rsi > Decimal("60") > self.rsi_list[1].rsi


class PlotGptHandle(BasePlotHandle):
    def __init__(self, symbol):
        super().__init__()
        self.symbol = symbol
        self.check_time = int(time.time())
        self.email_title = f"{symbol} GPT Plot Notice"

        self.close_monitor_url = f"{INNER_GET_DELETE_LIMIT_PRICE_URL}{symbol}"
        self.set_limit_price_url = ""

        self.prompt_text = f"你是一个专业的加密货币交易分析师。基于提供的 {self.symbol} 市场策略因子数据进行分析，交易时间为10小时内的短线交易，"

        self._kline_list_4h = None
        self._kline_list_1h = None
        self._macd_list_1d = None
        self._macd_list_4h = None
        self._macd_list_1h = None
        self._kdj_list_1d = None
        self._kdj_list_4h = None
        self._kdj_list_1h = None

        self.rsi_list_1h = None
        self.rsi_list_4h = None

        required_intervals = ["1h", "4h", "1d"]
        for interval in required_intervals:
            if interval not in PLOT_INTERVAL_CONFIG:
                raise ValueError(f"Required interval {interval} is missing in configuration")

    async def initialize_data(self):
        async with async_database.aio_atomic():
            _query = self.get_kline_query("4h", limit_count=30)
            _kline_list_4h = await _query.aio_execute()
            self._kline_list_4h = list(_kline_list_4h)

            _query = self.get_kline_query("1h", limit_count=30)
            _kline_list_1h = await _query.aio_execute()
            self._kline_list_1h = list(_kline_list_1h)

            _query = self.get_macd_query("1d", limit_count=30)
            _macd_list_1d = await _query.aio_execute()
            self._macd_list_1d = list(_macd_list_1d)

            _query = self.get_macd_query("4h", limit_count=30)
            _macd_list_4h = await _query.aio_execute()
            self._macd_list_4h = list(_macd_list_4h)

            _query = self.get_macd_query("1h", limit_count=30)
            _macd_list_1h = await _query.aio_execute()
            self._macd_list_1h = list(_macd_list_1h)

            _query = self.get_kdj_query("1d", limit_count=2)
            _kdj_list_1d = await _query.aio_execute()
            self._kdj_list_1d = list(_kdj_list_1d)

            _query = self.get_kdj_query("4h", limit_count=8)
            _kdj_list_4h = await _query.aio_execute()
            self._kdj_list_4h = list(_kdj_list_4h)

            _query = self.get_kdj_query("1h", limit_count=8)
            _kdj_list_1h = await _query.aio_execute()
            self._kdj_list_1h = list(_kdj_list_1h)

            _query = self.get_rsi_query("1h", limit_count=8)
            _rsi_list_1h = await _query.aio_execute()
            self.rsi_list_1h = list(_rsi_list_1h)

            _query = self.get_rsi_query("4h", limit_count=8)
            _rsi_list_4h = await _query.aio_execute()
            self.rsi_list_4h = list(_rsi_list_4h)

    def get_kline_query(self, interval, limit_count=18):
        query = (
            KlineTable.select().where(
                KlineTable.symbol == self.symbol,
                KlineTable.interval_val == interval,
            ).order_by(KlineTable.id.desc()).limit(limit_count)
        )
        return query

    def get_macd_query(self, interval, limit_count=18):
        query = (
            MacdTable.select().where(
                MacdTable.symbol == self.symbol,
                MacdTable.interval_val == interval,
            ).order_by(MacdTable.id.desc()).limit(limit_count)
        )
        return query

    def get_kdj_query(self, interval, limit_count=18):
        query = (
            KdjTable.select().where(
                KdjTable.symbol == self.symbol,
                KdjTable.interval_val == interval,
            ).order_by(KdjTable.id.desc()).limit(limit_count)
        )
        return query

    def get_rsi_query(self, interval, limit_count=18):
        query = (
            RsiTable.select(RsiTable.rsi).where(
                RsiTable.symbol == self.symbol,
                RsiTable.interval_val == interval,
            ).order_by(RsiTable.id.desc()).limit(limit_count)
        )
        return query


    @property
    def kline_list_4h(self):
        if self._kline_list_4h is None:
            self._kline_list_4h = self.get_kline_list("4h", limit_count=30)
        return self._kline_list_4h

    @property
    def kline_list_1h(self):
        if self._kline_list_1h is None:
            self._kline_list_1h = self.get_kline_list("1h", limit_count=30)
        return self._kline_list_1h

    @property
    def macd_list_1d(self):
        if self._macd_list_1d is None:
            self._macd_list_1d = self.get_macd_list("1d", limit_count=30)
        return self._macd_list_1d

    @property
    def macd_list_4h(self):
        if self._macd_list_4h is None:
            self._macd_list_4h = self.get_macd_list("4h", limit_count=30)
        return self._macd_list_4h

    @property
    def macd_list_1h(self):
        if self._macd_list_1h is None:
            self._macd_list_1h = self.get_macd_list("1h", limit_count=30)
        return self._macd_list_1h

    @property
    def kdj_list_1d(self):
        if self._kdj_list_1d is None:
            self._kdj_list_1d = self.get_kdj_list("1d", limit_count=2)
        return self._kdj_list_1d

    @property
    def kdj_list_4h(self):
        if self._kdj_list_4h is None:
            self._kdj_list_4h = self.get_kdj_list("4h", limit_count=8)
        return self._kdj_list_4h

    @property
    def kdj_list_1h(self):
        if self._kdj_list_1h is None:
            self._kdj_list_1h = self.get_kdj_list("1h", limit_count=8)
        return self._kdj_list_1h

    async def has_limit_price_check(self, statuses):
        all_limit_prices = MarketPriceLimitCache.hgetall()
        if not all_limit_prices:
            return False

        has_limit = all_limit_prices.get(self.symbol)

        try:
            last_ticket = await PlotBackTestTable.select().where(
                PlotBackTestTable.symbol == self.symbol,
            ).order_by(PlotBackTestTable.id.desc()).aio_get()
            has_ask_ticket = last_ticket.status in statuses
        except PlotBackTestTable.DoesNotExist:
            has_ask_ticket = False
        return has_limit or has_ask_ticket

        # all_limit_prices.pop("btcusdt", None)
        # return all_limit_prices.get(self.symbol)

    def get_bollinger_bands(self, interval):
        """
        支撑位: 布林带下轨
        阻力位: 布林带上轨
        """
        interval_map = {
            "1d": self.macd_list_1d,
            "4h": self.macd_list_4h,
            "1h": self.macd_list_1h
        }

        if interval not in interval_map:
            raise ValueError(f"Invalid interval: {interval}")

        macd_list = interval_map[interval][:27]

        close_prices = [row.closing_price for row in macd_list[1:]]
        ema_values = [row.ema_26 for row in macd_list[1:]]

        last_upper_band, last_lower_band = calculate_bollinger_bands(close_prices[::-1], ema_values[::-1])
        return last_upper_band, last_lower_band

    def trend_following_strategy_reformat_notice(self, direction, current_data):
        return template_gpt_plot_trend_following_strategy_notice(self.symbol, direction, current_data.open_ts)

    def short_term_strategy_reformat_notice(self, direction, current_kdj_1h, current_price, send_ts, close_monitor_url, set_limit_price_url):
        return template_gpt_plot_short_term_strategy_notice(
            self.symbol, direction, current_kdj_1h.open_ts, current_price, send_ts, close_monitor_url, set_limit_price_url)

    def bull_run_strategy_reformat_notice(self, direction, open_ts, current_price, send_ts, close_monitor_url, set_limit_price_url):
        return template_gpt_plot_bull_run_strategy_notice(
            self.symbol, direction, open_ts, current_price, send_ts, close_monitor_url, set_limit_price_url)

    def get_kline_list(self, interval, limit_count=18):
        query = (
            KlineTable.select().where(
                KlineTable.symbol == self.symbol,
                KlineTable.interval_val == interval,
            ).order_by(KlineTable.id.desc()).limit(limit_count)
        )
        query_list = list(query)
        if len(query_list) < limit_count:
            return
        return query_list

    def get_macd_list(self, interval, limit_count=18):
        query = (
            MacdTable.select().where(
                MacdTable.symbol == self.symbol,
                MacdTable.interval_val == interval,
            ).order_by(MacdTable.id.desc()).limit(limit_count)
        )
        query_list = list(query)
        if len(query_list) < limit_count:
            return
        return query_list

    def get_kdj_list(self, interval, limit_count=18):
        query = (
            KdjTable.select().where(
                KdjTable.symbol == self.symbol,
                KdjTable.interval_val == interval,
            ).order_by(KdjTable.id.desc()).limit(limit_count)
        )
        query_list = list(query)
        if len(query_list) < limit_count:
            return
        return query_list

    def get_signal_count_data(self, *signals):
        true_count = sum(signals)
        false_count = len(signals) - true_count

        if true_count > false_count:
            return {"status": "增强", "true_count": true_count, "false_count": false_count}
        elif true_count < false_count:
            return {"status": "减弱", "true_count": true_count, "false_count": false_count}
        else:
            return {"status": "持衡", "true_count": true_count, "false_count": false_count}

    def get_fng_signal(self, buy=False):
        """
        策略信号-恐惧指数：
            <= 20, 买入信号
            >= 80, 卖出信号
            其他不做参考
        :return:
        """
        cache_data = FearAndGreedIndexCache.get()
        if not cache_data:
            return

        fng_index = int(cache_data)
        if buy is True:
            if fng_index <= 20:
                return True
            elif fng_index >= 80:
                return False
        else:
            if fng_index <= 20:
                return False
            elif fng_index >= 80:
                return True
        return

    def get_dynamic_threshold(self):
        threshold_data = {
            "kdj_death_cross": Decimal("85")
        }

        cache_data = FearAndGreedIndexCache.get()
        if not cache_data:
            return threshold_data

        fng_index = int(cache_data)
        if 0 <= fng_index <= 49:
            threshold_data["kdj_death_cross"] = Decimal("80")

        return threshold_data

    def get_depth_prices(self, current_price):
        """
        根据当前深度信息，最大挂单量的价格，作为支撑位和阻力位。
        结合当前价，计算建议买入价。
        :return:
        """
        resp_data = http_get_request(
            "https://api.binance.com/api/v3/depth",
            {"symbol": self.symbol.upper(), "limit": 99},
        )
        if not resp_data:
            return {"bid_price": "", "ask_price": "", "recommend_bid_price": "", "recommend_ask_price": ""}

        bids_list = resp_data["bids"]
        asks_list = resp_data["asks"]

        bid_data = max(bids_list, key=lambda x: Decimal(x[1]))
        bid_price = Decimal(bid_data[0])

        ask_data = max(asks_list, key=lambda x: Decimal(x[1]))
        ask_price = Decimal(ask_data[0])

        recommend_bid_price = bid_price + (current_price - bid_price) * Decimal("0.6")
        recommend_ask_price = current_price + (ask_price - current_price) * Decimal("0.6")
        self.prompt_text += f"\n<br> 计算建议价：当前价格:{current_price}，根据最新99条深度数据，最大挂买单量的价格:{bid_price}，按照买入建议价公式：bid_price + (current_price - bid_price) * Decimal('0.6')，得到买入建议价:{str2decimal(recommend_bid_price)}；" \
                            f"最大挂卖单量的价格:{ask_price}，按照卖出建议价的公式：current_price + (ask_price - current_price) * Decimal('0.6')，得到卖出建议价：{str2decimal(recommend_ask_price)}。你有更好的买入或者卖出建议价吗"
        return {
            "bid_price": bid_price,
            "ask_price": ask_price,
            "recommend_bid_price": decimal2decimal(recommend_bid_price),
            "recommend_ask_price": decimal2decimal(recommend_ask_price),
        }

    def get_tp_and_sl(self, curr_price, depth_bid_price, depth_ask_price, bb_upper_4h_price):
        """
        计算 止盈（Take Profit, TP）和止损（Stop Loss, SL）
        止损价 = (1小时布林带下轨 + 99条深度数据的最大买单价 + min(EMA12, EMA26)) / 3
        止盈价 = (4小时布林带上轨 + 99条深度数据的最大卖单价 + 过去17根1小时K线最高值) / 3
        :return:
        """
        ema12_price = self.macd_list_1h[0].ema_12
        ema26_price = self.macd_list_1h[0].ema_26

        bb_upper_1h_price, bb_lower_1h_price = self.get_bollinger_bands("1h")

        previous_high_price = max([i.high_price for i in self.kline_list_1h[1:18]])

        sl_price = (bb_lower_1h_price + depth_bid_price + min(ema12_price, ema26_price)) / Decimal("3")
        tp_price = (bb_upper_4h_price + depth_ask_price + previous_high_price) / Decimal("3")
        atr_price_info = get_atr_price(self.kline_list_1h[:7][::-1], curr_price)
        return {"sl_price": decimal2decimal(sl_price), "tp_price": decimal2decimal(tp_price),
                "atr_sl_price": decimal2decimal(atr_price_info["sl_price"]),
                "atr_tp_price": decimal2decimal(atr_price_info["tp_price"])}

    def get_previous_high_price(self, kline_list, window_size=6):
        """
        Donchian Channel: 唐奇安通道策略
        """
        high_list = [i.high_price for i in kline_list]
        return max(high_list[:window_size])

    def _check_kdj_uptrend(self, kdj_list):
        """检查KDJ是否处于递增趋势(基于每一组数据的离散值->离散值的数组)"""

        for i in range(1, len(kdj_list)):
            curr_kdj = kdj_list[i]
            last_kdj = kdj_list[i-1]

            curr_cv = calculate_cv([curr_kdj.k_val, curr_kdj.d_val, curr_kdj.j_val], num=8)
            last_cv = calculate_cv([last_kdj.k_val, last_kdj.d_val, last_kdj.j_val], num=8)
            if curr_cv <= last_cv:
                return False
        return True

    def _check_kdj_golden_cross_count(self, kdj_list, threshold=0):
        """检查 KDJ历史金叉数量"""
        crossovers_data = analyze_crossovers(kdj_list)
        return crossovers_data["golden_cross"] > threshold

    def _check_kdj_golden_cross(self, kdj_list):
        """检查 KDJ当前金叉"""
        return (kdj_list[1].k_val < kdj_list[1].d_val and
                kdj_list[0].k_val > kdj_list[0].d_val)

    def _check_kdj_golden_cross_by_threshold(self, kdj_list, threshold):
        """检查 KDJ当前低位金叉"""
        return (kdj_list[1].k_val <= threshold and
                kdj_list[1].d_val <= threshold and
                kdj_list[1].j_val <= threshold and
                kdj_list[1].k_val < kdj_list[1].d_val and
                kdj_list[0].k_val > kdj_list[0].d_val)

    def _check_kdj_death_cross(self, kdj_list):
        """检查 KDJ当前死叉"""
        return (kdj_list[1].k_val > kdj_list[1].d_val and
                kdj_list[0].k_val < kdj_list[0].d_val)

    def _check_kdj_death_cross_by_threshold(self, kdj_list, threshold):
        """检查 KDJ当前高位死叉"""
        current = (kdj_list[1].k_val >= threshold and
                   kdj_list[1].d_val >= threshold and
                   kdj_list[1].j_val >= threshold and
                   kdj_list[1].k_val > kdj_list[1].d_val and
                   kdj_list[0].k_val < kdj_list[0].d_val)

        last = (kdj_list[2].k_val >= threshold and
                kdj_list[2].d_val >= threshold and
                kdj_list[2].j_val >= threshold and
                kdj_list[2].k_val > kdj_list[2].d_val and
                kdj_list[0].k_val < kdj_list[0].d_val)
        return current or last

    def _check_price_breakout(self, count, current_price, previous_high):
        """检查 是否有价格突破"""
        return count > 0 and current_price >= previous_high

    def _check_increasing_highs(self, kline_list, rate=Decimal("0.001")):
        """检查 最高价是否逐步递增"""
        for i in range(1, len(kline_list)):
            last_price = kline_list[i].high_price
            curr_price = kline_list[i-1].high_price
            if curr_price < last_price:
                return False

            growth = (curr_price - last_price) / last_price
            if growth <= rate:
                return False

        return True

    def _check_continuous_selling(self, kline_list, threshold=3):
        """
        检查 是否连续卖出
        :param kline_list: 时间正序
        :return:
        """
        continuous_down_count = 0

        for i in range(len(kline_list)):
            current_kline = kline_list[i]

            # 检查是否为下跌K线（收盘价低于开盘价）
            if current_kline.close_price < current_kline.open_price:
                continuous_down_count += 1

                # 如果不是第一根K线，检查收盘价是否低于前一根K线
                if i > 0 and current_kline.close_price >= kline_list[i - 1].close_price:
                    continuous_down_count = 0  # 重置计数
            else:
                continuous_down_count = 0  # 遇到非下跌K线，重置计数

            # 如果已经找到足够的连续下跌K线，返回True
            if continuous_down_count >= threshold:
                return True

        return False

    def _get_holding_time(self):
        limit_price = MarketPriceLimitCache.hget(self.symbol)
        if not limit_price:
            set_time, limit_low_price, limit_high_price = 0, "", ""
        else:
            set_time, limit_low_price, limit_high_price = limit_price.split(":")
        set_time = int(set_time)
        if not set_time:
            hours_diff = None
        else:
            hours_diff = round((self.check_time - set_time) / 3600, 1)
        return {"set_time": set_time, "hours_diff": hours_diff}

    def _check_trade_interval_time(self):
        redis_client = AllCache.get_client()
        last_ts = redis_client.get("lastTradeTs")
        if not last_ts:
            return True
        if self.check_time - int(last_ts) > 3600:
            return True
        else:
            return False

    async def check(self, limit_count=7):
        await self.initialize_data()

        open_ts = self.kline_list_1h[0].open_ts
        curr_price = self.kline_list_1h[0].close_price

        for interval, macd_list in (("1d", self.macd_list_1d), ("4h", self.macd_list_4h)):
            interval_sec = PLOT_INTERVAL_CONFIG[interval]["interval_sec"]
            if macd_list[0].opening_ts < (self.check_time - interval_sec * limit_count):
                self.result[
                    self.symbol
                ] = f"""
                        <br><a>Error: no lastest macd data, {self.symbol}:{interval}</a>
                        <br><a>opening_ts:{ts2bjfmt(macd_list[0].opening_ts)}</a>
                        <br><a>now_ts:{ts2bjfmt(self.check_time)}</a>
                        """

                return await self.send_msg(self.email_title, "".join(self.result.values()))

        # await self.short_term_strategy(limit_count)
        # await self.bull_run_strategy()

        if not await self.has_limit_price_check((0, 1, 3)):
            score_info = await self.get_buy_score_info(curr_price)
            if not score_info:
                return

            depth_prices_data = self.get_depth_prices(curr_price)
            depth_bid_price = depth_prices_data["bid_price"]
            depth_ask_price = depth_prices_data["ask_price"]
            recommend_bid_price = depth_prices_data["recommend_bid_price"]

            atr_price_info = get_atr_price(self.kline_list_1h[:7][::-1], curr_price)
            sl_price = decimal2decimal(atr_price_info["sl_price"])
            tp_price = decimal2decimal(atr_price_info["tp_price"])
            self.set_limit_price_url = f"{INNER_GET_SUBMIT_LIMIT_PRICE_URL}?" \
                                  f"symbol={self.symbol}&low_price={sl_price}" \
                                  f"&high_price={tp_price}"

            redis_client = AllCache.get_client()
            redis_client.set(f"sl_tp:{self.symbol}", f"{sl_price}:{tp_price}")

            direction = f"<br> 🟢 短线买入信号: <b>{self.symbol.upper()}</b>" \
                        f"\n<br> 总分: {sum(score_info.values())}。" \
                        f"\n<br> 分数详情： {score_info.items()}。" \
                        f"\n<br><br> 📈 建议买入价: {recommend_bid_price}。<br><br>"
            func_str = "get_buy_score_info"

            await BackTestHandler(self.symbol).add_bid_ticket(
                curr_price,
                recommend_bid_price,
                self.check_time,
                5,
                direction
            )

        elif await self.has_limit_price_check((1,)):
            recommend_ask_price = None

            # 海象运算符, py3.8新特性
            # if part_direction := self._get_sell_direction_active_taking_profit(curr_price):
            #     ask_plot_type = 6
            # elif part_direction := self._get_sell_direction_stop_loss(curr_price):
            #     ask_plot_type = 7
            if part_direction := self._get_exit_score():
                ask_plot_type = 8
                func_str = "_get_exit_score"
            else:
                redis_client = AllCache.get_client()
                cache_data = redis_client.get(f"sl_tp:{self.symbol}")
                func_str = "tp_sl"

                if not cache_data:
                    return
                sl_price, tp_price = map(Decimal, cache_data.split(":"))

                if curr_price >= tp_price:
                    part_direction += "当前价格触及止盈价，止盈离场。"
                    recommend_ask_price = curr_price
                    ask_plot_type = 8
                elif curr_price <= sl_price:
                    part_direction += "当前价格触及止损价，止损离场。"
                    recommend_ask_price = sl_price
                    ask_plot_type = 9
                else:
                    return

            if not recommend_ask_price:
                depth_prices_data = self.get_depth_prices(curr_price)
                recommend_ask_price = depth_prices_data["recommend_ask_price"]

            direction = f"<br> 🔴 短线卖出信号: <b>{self.symbol.upper()}</b> " \
                        f"<br> {part_direction}" \
                        f"<br><br> 📉 建议卖出价：{recommend_ask_price}" \

            await BackTestHandler(self.symbol).update_ask_ticket(
                curr_price,
                recommend_ask_price,
                self.check_time,
                ask_plot_type,
                direction
            )

        else:
            return

        email_msg_md5_str = f"plotGpt:{func_str}:{self.symbol}:{open_ts}"
        email_msg_md5 = hashlib.md5(email_msg_md5_str.encode("utf8")).hexdigest()

        try:
            return await EmailMsgHistoryTable.aio_get(EmailMsgHistoryTable.msg_md5 == email_msg_md5)
        except EmailMsgHistoryTable.DoesNotExist:
            pass

        self.result[self.symbol] = template_strategy_notice(
            direction, open_ts, curr_price, self.check_time, self.close_monitor_url, self.set_limit_price_url)

        email_content = "".join(self.result.values())
        await EmailMsgHistoryTable.aio_create(msg_md5=email_msg_md5, msg_content=email_content)

        logger.info(
            f"PlotGptHandle.get_buy_score_info finish, start end_msg, symbol:{self.symbol}, ts:{self.check_time}")
        await self.send_msg(self.email_title, email_content)

    async def short_term_strategy(self, limit_count):
        """
        短线快进快出策略
            主要工具：1小时KDJ+4小时MACD/日线MACD
            触发条件：核心信号满足+任意一个辅助信号满足即可触发买入，这样可以避免因为条件过多而错失信号。
        📈 买入信号
            1. 4小时MACD：DIF上穿DEA；或者 日线MACD：DIF上穿DEA。确认趋势反转后，再考虑买入。
            2. 日线KDJ刚形成死叉，说明趋势向下，不要向下考虑买入。
            3. 1小时KDJ的值均大于35，表示超卖反弹，增强买入信号，接着考虑第4点。
            4. 1小时MACD：最近7根线MACD柱状图的相对下行趋势(基于18根线计算相对值)减弱，表示下跌趋势减缓，接着考虑买入的辅助信号。
            5. 1小时级别击穿前低价：当前1小时的最低价，小于前10根1小时线的最低价，下跌趋势延续，不要向下考虑。
                5.1. (或)当前价格 **靠近 4小时布林带下轨值**，未击穿支撑位，增强买入信号。
                5.2. (或)1小时KDJ **最近8条线，有接近死叉或金叉**，增强买入信号。
                5.3. (或)1小时K线的 **近三条的最高价没有逐步下降**(或者**日线MACD大于0**)，表示下跌压力减缓，1小时KDJ均值小于20附近，增强买入信号。
                5.4. (或)1小时成交量 **高于过去10根均值**，资金流入，增强买入信号。
                5.5. (或)4小时成交量 **高于过去3根均值**，资金持续流入，增强买入信号。
                5.6. (增)1小时K线，**最近5根线出现连续卖出3根**，表示下跌压力过大，减弱买入信号。
                5.7. (增)贪婪指数小于20值时，表示卖方市场，增加买入信号。
                5.8. (增)1小时K线，**看涨吞没**，增强买入信号。

        📉 卖出信号
            1. 关键信号判断:
                1.0. 1小时MACD的当前时间段的值处于金叉，表示持续上涨，考虑持仓观望。
                1.1. 4小时MACD的当前时间段的值处于金叉，表示持续上涨，考虑持仓观望。
                1.2. 4小时KDJ的当前时间段的值处于金叉，表示持续上涨，考虑持仓观望。

            1. 4小时MACD上行：DIF上穿DEA；或者 日线MACD上行：DIF上穿DEA（多头排列或者底背离）。

            2. 1小时KDJ的J值小于80时，判断是否趋势向下。
                2.1. 1小时KDJ值30到70区间，1小时MACD负值，横盘震荡下行，提示离场。

                2.2. 没有触发(2.1)条件时。
                2.2.1. 1小时的最新3条线的J值存在大于50且不递减，表示市场仍有上涨动能，不考虑挂买入价卖出。
                2.2.2. 1小时的最新2根线的J值向上，表示可能存在反弹，不考虑挂单卖出。
                2.2.3. 1小时的K线的最新2根线，价格区间上涨，表示下跌信号不强，不考虑挂单卖出。
                2.2.4. 4小时的KDJ的J值连续3根持续向上，表情中行情仍上涨，不考虑挂单卖出。

            3. 1小时KDJ的J值在80附近，表示超买出现，开始考虑出场。
                    3.2.1. (或)1小时MACD：最近7根线(不包含当前线)(结合历史18根线的趋势进行相对判断)MACD柱状图的上行趋势减弱，表示上涨趋势减缓，表示出场信号加强。
                    3.2.2. (或)当前1小时最高价，小于前面3根1小时线的最高价，表示价格受阻，超买回调趋势加强，表示出场信号加强。
                    3.2.3. (或)当前价格，在1小时布林带上轨且回落0.5%，表示出场信号加强。
                    3.2.4. (或)4小时MACD的最近2根柱状图，向下扩大，表示出场信号加强。
                    3.2.5. (或)4小时KDJ的最近2个时间段，K线和J线均下跌，表示出场信号加强。
                    3.2.6. (或)1小时KDJ的附近(当前时间段处于死叉向下的2个时间段内)的高位值(85根据fng指数值动态调整)死叉，表示出场信号加强。
                    3.2.7. (或)持仓时间超过8小时，增强出场信号。

        ⚠️ 注意：快进快出策略适合高频短线交易者，如果在趋势不明朗的震荡行情中，信号可能会频繁“假死叉”和“假金叉”。
        """
        close_monitor_url = f"{INNER_GET_DELETE_LIMIT_PRICE_URL}{self.symbol}"
        set_limit_price_url = ""
        direction, current_price = None, None
        direction_type = None

        # TODO: 全仓改分仓
        if not await self.has_limit_price_check((0, 1, 3)):
            self.prompt_text += "输出买入的建议概率。"
            direction_type = "is_bid"
            if self.macd_list_1d[0].macd < 0 and self.macd_list_4h[0].macd < 0:
                return

            if self._check_trade_interval_time() is False:
                return

            direction_info = self._get_buy_direction()
            if not direction_info:
                return
            direction = direction_info["direction"]
            set_limit_price_url = direction_info["set_limit_price_url"]
            current_price = direction_info["current_price"]

            await BackTestHandler(self.symbol).add_bid_ticket(
                current_price,
                direction_info["recommend_bid_price"],
                self.check_time,
                1,
                direction
            )

        # elif MarketPriceLimitCache.hget(self.symbol):
        elif await self.has_limit_price_check((1, )):
            current_price = self.kline_list_1h[0].close_price

            self.prompt_text += "输出卖出或持仓的建议概率。"

            direction_type = "is_ask"
            if self.check_time >= (self.macd_list_1h[0].opening_ts + PLOT_INTERVAL_CONFIG["1h"]["interval_sec"]):
                # 当前检查时间>=最新时间段的收盘时间，表明最新的MACD数据还未写入，暂停判断.
                return

            macd_1h_strategies = MacdStrategy(self.macd_list_1h)
            if macd_1h_strategies.get_curr_golden_cross():
                return
            self.prompt_text += f"\n<br> 1.先判断当前出否处于特殊信号：当前1小时的MACD没有刚形成金叉。"

            macd_4h_strategies = MacdStrategy(self.macd_list_4h)
            if macd_4h_strategies.get_curr_golden_cross():
                return
            self.prompt_text += f"\n 当前4小时的MAD没有刚形成金叉。"

            kdj_4h_strategies = KdjStrategy(self.kdj_list_4h)
            if kdj_4h_strategies.get_curr_golden_cross():
                return
            self.prompt_text += f"\n 当前4小时的KDJ没有刚形成金叉。"

            holding_time_info = self._get_holding_time()
            set_time = holding_time_info["set_time"]
            hours_diff = holding_time_info["hours_diff"]

            # if self.kdj_list_1h[0].j_val >= Decimal("100"):
            #     self._get_sell_signal_by100()
            # elif self.kdj_list_1h[0].j_val >= Decimal("80"):
            #     self._get_sell_signal_by80()
            # elif self.kdj_list_1h[0].j_val >= Decimal("60"):
            #     self._get_sell_signal_by60()




            if self.kdj_list_1h[0].j_val <= Decimal("80"):
                self.prompt_text += f"\n<br> 2.当前的持仓时间为 {hours_diff} 小时。"
                self.prompt_text += f"\n<br> 3.再判断更精细的因子信号：当前1小时的KDJ的J值小于80。"

                direction_info = self._get_sell_direction_sideways_or_downward(set_time, hours_diff)
                if direction_info:
                    direction = direction_info["direction"]
                    current_price = direction_info["current_price"]

                    await BackTestHandler(self.symbol).update_ask_ticket(
                        current_price,
                        direction_info["recommend_ask_price"],
                        self.check_time,
                        2,
                        direction
                    )

            else:
                self.prompt_text += f"\n<br> 2.当前的持仓时间为 {hours_diff} 小时"
                self.prompt_text += f"\n<br> 3.再判断更精细的因子信号：当前1小时的KDJ的J值大于80。"

                direction_info = self._get_sell_direction_upward(hours_diff)
                if not direction_info:
                    return
                direction = direction_info["direction"]
                current_price = direction_info["current_price"]

                await BackTestHandler(self.symbol).update_ask_ticket(
                    current_price,
                    direction_info["recommend_ask_price"],
                    self.check_time,
                    3,
                    direction
                )

        else:
            return

        if not direction:
            return
        direction += self.prompt_text

        email_msg_md5_str = (
            f"plotGpt:short_term_strategy:{self.symbol}:{self.kdj_list_1h[0].open_ts}:{direction_type}"
        )
        email_msg_md5 = hashlib.md5(email_msg_md5_str.encode("utf8")).hexdigest()
        try:
            return await EmailMsgHistoryTable.aio_get(EmailMsgHistoryTable.msg_md5 == email_msg_md5)
        except EmailMsgHistoryTable.DoesNotExist:
            self.result[self.symbol] = self.short_term_strategy_reformat_notice(
                direction, self.kdj_list_1h[0], current_price, self.check_time, close_monitor_url, set_limit_price_url)

        email_content = "".join(self.result.values())
        await EmailMsgHistoryTable.aio_create(msg_md5=email_msg_md5, msg_content=email_content)

        logger.info(
            f"PlotGptHandle.short_term_strategy finish, start end_msg, symbol:{self.symbol}, ts:{self.check_time}")
        await self.send_msg(self.email_title, email_content)

    def _get_buy_direction(self):
        all_signals_dict = {}

        kdj_1d_strategies = KdjStrategy(self.kdj_list_1d)
        if kdj_1d_strategies.get_curr_death_cross():
            return

        kline_1h_strategies = CandlestickStrategy(self.kline_list_1h, self.macd_list_1h)

        current_kdj_1h = self.kdj_list_1h[0]
        if current_kdj_1h.k_val > Decimal("35") \
                or current_kdj_1h.d_val > Decimal("35") or current_kdj_1h.j_val > Decimal("35"):
            return

        # TODO: 手动回测-是否改为相对趋势
        current_trend_macd_1h, _ = analyze_list_trend([i.macd for i in self.macd_list_1h[:7]][::-1])
        if current_trend_macd_1h in ["downward_spiral", ]:
            return

        current_1h_low_price = self.kline_list_1h[0].low_price
        last_1h_low_price = min([i.low_price for i in self.kline_list_1h[1:11]])
        if current_1h_low_price < last_1h_low_price:
            return

        current_price = self.macd_list_1h[0].closing_price

        bb_upper_4h, bb_lower_4h = self.get_bollinger_bands("4h")
        near_info = check_near_low(self.kline_list_4h[:21][::-1], bb_lower_4h, bb_upper_4h, logger)
        # near_support
        all_signals_dict["check_price_fall_signal"] = near_info["is_near"]

        check_cv_cross_signal = any(
            calculate_cv([kdj.k_val, kdj.d_val, kdj.j_val]) == 0
            for kdj in self.kdj_list_1h[:8]
        )
        # TODO: 窗口大小，KDJ三线是否凑集
        # kdj_convergence
        all_signals_dict["check_cv_cross_signal"] = check_cv_cross_signal

        check_kdj_20_signal = False
        high_prices_1h_list = [i.high_price for i in self.kline_list_1h[:3]]
        if all(x < y for x, y in zip(high_prices_1h_list, high_prices_1h_list[1:])) is False \
                or self.macd_list_1d[0].macd > 0:
            if current_kdj_1h.k_val < Decimal("20") and current_kdj_1h.d_val < Decimal("20") \
                    and current_kdj_1h.j_val < Decimal("20"):
                check_kdj_20_signal = True
        # oversold_non_decreasing
        all_signals_dict["check_kdj_20_signal"] = check_kdj_20_signal

        volume_4h_list = [i.volume for i in self.kline_list_4h[1:4]]
        last_mean_4h_volume = sum(volume_4h_list) / Decimal(len(self.kline_list_4h[1:4]))
        current_4h_volume = self.kline_list_4h[0].volume
        volume_1h_list = [i.volume for i in self.kline_list_1h[1:11]]
        last_mean_1h_volume = sum(volume_1h_list) / Decimal(len(self.kline_list_1h[1:11]))
        current_1h_volume = self.kline_list_1h[0].volume
        if current_4h_volume > last_mean_4h_volume:
            check_4h_volume_up_signal = True
        else:
            check_4h_volume_up_signal = False
        #     volume_4h_increasing
        all_signals_dict["check_4h_volume_up_signal"] = check_4h_volume_up_signal

        if current_1h_volume > last_mean_1h_volume:
            check_1h_volume_up_signal = True
        else:
            check_1h_volume_up_signal = False
        #     volume_1h_increasing
        all_signals_dict["check_1h_volume_up_signal"] = check_1h_volume_up_signal

        if self._check_continuous_selling(self.kline_list_1h[:5][::-1]):
            all_signals_dict["check_continuous_selling"] = False

        check_fng_signal = self.get_fng_signal(buy=True)
        if check_fng_signal is not None:
            all_signals_dict["check_fng_signal"] = check_fng_signal

        if kline_1h_strategies.get_engulfing_pattern_strategy()["has_bullish_engulfing"] is True:
            all_signals_dict["check_has_bullish_engulfing"] = True

        if any(list(all_signals_dict.values())) is not True:
            return

        signal_data = self.get_signal_count_data(*all_signals_dict.values())
        # if signal_data["true_count"] == 1:
        if signal_data["true_count"] <= 2: #TODO: 等待回测验证
            logger.info(f"plot_gpt, _get_buy_direction not enough msg, "
                        f"symbol:{self.symbol}, all_signals_dict:{all_signals_dict}")
            return

        depth_prices_data = self.get_depth_prices(current_price)
        depth_bid_price = depth_prices_data["bid_price"]
        depth_ask_price = depth_prices_data["ask_price"]
        recommend_bid_price = depth_prices_data["recommend_bid_price"]

        tp_and_sl_price_data = self.get_tp_and_sl(current_price, depth_bid_price, depth_ask_price, bb_upper_4h)
        tp_price = tp_and_sl_price_data["atr_tp_price"]
        sl_price = tp_and_sl_price_data["atr_sl_price"]

        direction = f" 🟢 短线高频交易(策略待优化): 📈 买入信号, " \
                    f"<br>总体信号-<b>{signal_data['status']}</b>" \
                    f"<br>建议买入价：{recommend_bid_price}" \
                    f"<br><b>挂单失败，严禁追涨，十追九败</b><br><br><br>" \
                    f"<br>总信号：{all_signals_dict}"

        if self.symbol in TMP_STAR_TOP10:
            direction += "<br>🌟 🌟 🌟 🌟 🌟 </br>"

        set_limit_price_url = f"{INNER_GET_SUBMIT_LIMIT_PRICE_URL}?" \
                              f"symbol={self.symbol}" \
                              f"&low_price={sl_price}" \
                              f"&high_price={tp_price}"

        logger.info(f"plot_gpt, _get_buy_direction has new msg, symbol:{self.symbol}, current_price:{current_price}")

        return {"direction": direction, "set_limit_price_url": set_limit_price_url,
                "current_price": current_price, "recommend_bid_price": recommend_bid_price}

    def _get_sell_direction_active_taking_profit(self, curr_price):
        """
        主动止盈:
            若 KDJ J 值 > 90 且 MACD DIF 下降，视为强势过热信号，部分止盈。
        :return:
        """
        direction = ""
        macd_1h_strategies = MacdStrategy(self.macd_list_1h)

        if self.kdj_list_1h[0].j_val > 90 and macd_1h_strategies.get_dif_downtrend():
            direction += "强势过热信号，部分止盈。"
            return direction

        kline_1h_strategies = CandlestickStrategy(self.kline_list_1h, self.macd_list_1h)
        bb_info = kline_1h_strategies.get_bollinger_bands()
        near_info = check_near_high(self.kline_list_1h[:21][::-1], bb_info["bb_mid"], bb_info["bb_upper"], logger)
        if near_info["is_near"]:
            direction += "价格逼近 1小时布林带上轨，优先止盈。"
            return direction

        if kline_1h_strategies.has_double_top():
            direction += "当前处于1小时双顶形态，止盈离场。"
            return direction

        kline_4h_strategies = CandlestickStrategy(self.kline_list_4h, self.macd_list_4h)
        if kline_4h_strategies.get_engulfing_pattern_strategy()["has_bearish_engulfing"] is True:
            direction += "4小时看跌吞没，止盈离场。"
            return

        return direction

    def _get_sell_direction_stop_loss(self, curr_price):
        """
        止损：
        :param curr_price:
        :return:
        """
        direction = ""

        kline_1h_strategies = CandlestickStrategy(self.kline_list_1h, self.macd_list_1h)
        ema_1h_strategy = kline_1h_strategies.get_ema_strategy(is_ask=True)
        if ema_1h_strategy.get("has_death_cross"):
            direction += "1 小时 EMA12 和 EMA26 死叉，止损离场。"
            return direction

        return direction

    def _get_exit_score(self):
        """
        📊 领先信号（更早）：4H MACD 柱状图缩短：连续 2 根柱状图变短。-> +10 分
        📊 领先信号（更早）：1H KDJ J 线高位拐头：J 线 > 80 且开始向下。-> +10 分
        📊 动量因子：日线 KDJ 超买： K、D > 80 且 J 线向下。-> +15 分
        📊 动量因子：4H KDJ 超买： K、D > 80 且 J 线向下。-> +10 分
        🔻 价格行为因子：放量滞涨：1小时成交量暴增，但价格未创新高。-> +20 分

        """
        score_info = {}

        macd_4h_strategies = MacdStrategy(self.macd_list_4h)
        if macd_4h_strategies.get_downtrend():
            score_info["macd_4h_downtrend"] = 10

        if (self.kdj_list_1h[0].j_val > 80) and (self.kdj_list_1h[0].j_val < self.kdj_list_1h[1].j_val):
            score_info["kdj_1h_j_80_downtrend"] = 10

        if (self.kdj_list_1d[0].k_val > 80) and (self.kdj_list_1d[0].d_val > 80) \
                and (self.kdj_list_1d[0].j_val < self.kdj_list_1d[1].j_val):
            score_info["kdj_1d_over_bought"] = 15

        if (self.kdj_list_4h[0].k_val > 80) and (self.kdj_list_4h[0].d_val > 80) \
                and (self.kdj_list_4h[0].j_val < self.kdj_list_4h[1].j_val):
            score_info["kdj_4h_over_bought"] = 15

        kline_1h_strategies = CandlestickStrategy(self.kline_list_1h, self.macd_list_1h)
        window = 3
        max_price = kline_1h_strategies.get_donchian_channel(window_size=window)["max_price"]
        vol_1h_strategy = kline_1h_strategies.get_vol_strategy(window)

        if vol_1h_strategy.get("has_spike_volume") and self.kline_list_1h[0].high_price < max_price:
            score_info["vol_1h_stagflation"] = 20

        sum_score = sum(score_info.values())
        if sum_score >= 20:
            return f"{score_info.items()}"
        return ""

    def _get_sell_direction_sideways_or_downward(self, set_time, hours_diff):
        current_price, direction = "", ""
        recommend_ask_price = 0

        recent_kdj_list_1h = [i for i in self.kdj_list_1h
                              if ((0 <= (set_time - i.open_ts) < 3600) or (i.open_ts >= set_time))]
        recent_macd_list_1h = [i for i in self.macd_list_1h
                               if ((0 <= (set_time - i.opening_ts) < 3600) or (i.opening_ts >= set_time))]
        if (len(recent_kdj_list_1h) >= 5 and
                all(Decimal("30") <= i.j_val < Decimal("70") for i in recent_kdj_list_1h) and
                all(i.macd < 0 for i in recent_macd_list_1h)):

            self.prompt_text += f"\n 当前持仓时间超过了5小时；且持仓时间范围内的1小时KDJ的J值均处于30到70区间；且持仓时间范围内的1小时MACD均小于0。"

            current_price = self.kline_list_1h[0].close_price
            depth_prices_data = self.get_depth_prices(current_price)
            recommend_ask_price = depth_prices_data["recommend_ask_price"]
            direction = f"🔴⚠️🔴短线高频交易(策略待优化): 📉 卖出信号, 横盘震荡向下。"

            logger.info(f"plot_gpt, _get_sell_direction_sideways_or_downward, "
                        f"sideways and downward, symbol:{self.symbol}, set_time:{set_time}")

        if not direction:

            kdj_1h_strategies = KdjStrategy(self.kdj_list_1h)
            has_all_up = any(_kdj.j_val >= Decimal("50") for _kdj in self.kdj_list_1h[:3])
            has_b = kdj_1h_strategies.get_downtrend(3)
            if has_all_up and not has_b:
                return
            self.prompt_text += f"\n 当前时间段的1小时的最新3条线的J值存在大于50为 {has_all_up}，且其最新三根线的KDJ处于递减趋势为：{has_b}。"

            if self.kdj_list_1h[0].j_val > self.kdj_list_1h[1].j_val:
                return
            self.prompt_text += f"\n 当前时间段的1小时的KDJ的当前J值小于前J值。"

            for i in range(len(self.kline_list_1h[:2]) - 1):
                if self.kline_list_1h[i].open_price > self.kline_list_1h[i + 1].open_price:
                    return
                if self.kline_list_1h[i].close_price > self.kline_list_1h[i + 1].close_price:
                    return
            self.prompt_text += f"\n 当前时刻的1小时的K线的最新开盘价小于前开盘价，最新收盘价小于前收盘价。"

            j_val_4h_list = [i.j_val for i in self.kdj_list_4h[:3]]
            if all(x > y for x, y in zip(j_val_4h_list, j_val_4h_list[1:])) is True:
                return
            self.prompt_text += f"\n 当前时刻的4小时的KDJ的最新3根线的J值没有连续递增。"

            current_price = self.kline_list_1h[0].close_price

            depth_prices_data = self.get_depth_prices(current_price)
            recommend_ask_price = depth_prices_data["recommend_ask_price"]

            direction = f" 🔴⚠️🔴短线高频交易(策略待优化): 📉 卖出信号, \n\n\b<br>上涨受阻，挂卖单在买入价->⌛️等待卖出！" \
                        f"<br>持仓时间：{hours_diff} 小时" \
                        f"<br>建议卖出价：{recommend_ask_price}" \
                        f"<br>新增优化：结合15分钟MACD是否金叉->判断出场"

            logger.info(f"plot_gpt, _get_sell_direction_sideways_or_downward, rising blocked, symbol:{self.symbol},"
                        f"curr 1h j_val:{self.kdj_list_1h[0].j_val}, "
                        f"curr 1h close_price:{self.kline_list_1h[0].close_price},"
                        f"curr 4h j_val:{self.kdj_list_4h[0].j_val}")
        return {
            "current_price": current_price,
            "direction": direction,
            "recommend_ask_price": recommend_ask_price,
        }

    def _get_sell_direction_upward(self, hours_diff):
        all_signals_dict = {}

        current_trend_macd_1h = enhanced_analyze_list_trend_by_groups([i.macd for i in self.macd_list_1h[1:19]][::-1])
        check_trend_stalled_signal = current_trend_macd_1h["trend"] not in ["parabolic_move", ]
        all_signals_dict["check_trend_stalled_signal"] = check_trend_stalled_signal
        self.prompt_text += f"\n 当前时刻的1小时的MACD最近7根线(不包含当前线)(结合历史18根线的趋势进行相对判断)MACD柱状图的不处于明显上升趋势为 {check_trend_stalled_signal}。"

        high_prices_list = [i.high_price for i in self.kline_list_1h[:4]]
        check_price_resistance_signal = high_prices_list[0] < max(high_prices_list[1:])
        all_signals_dict["check_price_resistance_signal"] = check_price_resistance_signal
        self.prompt_text += f"\n 当前时刻的1小时周期的最高价小于前面3根1小时线的最高价为 {check_price_resistance_signal}。"

        current_price = self.macd_list_1h[0].closing_price
        bb_upper_1h, bb_lower_1h = self.get_bollinger_bands("1h")
        if current_price > bb_upper_1h \
                and ((high_prices_list[0] - current_price) / high_prices_list[0]) >= Decimal("0.005"):
            check_boll_resistance_signal = True
        else:
            check_boll_resistance_signal = False
        all_signals_dict["check_boll_resistance_signal"] = check_boll_resistance_signal
        self.prompt_text += f"\n 当前价格，在1小时周期的布林带上轨且回落0.5%的因子为 {check_boll_resistance_signal}。"

        if self.macd_list_4h[0].macd <= self.macd_list_4h[1].macd:
            check_macd_4h_signal = True
        else:
            check_macd_4h_signal = False
        all_signals_dict["check_macd_4h_signal"] = check_macd_4h_signal
        self.prompt_text += f"\n 当前在4小时周期的最新MACD值小于前MACD值为 {check_macd_4h_signal}。"

        if (self.kdj_list_4h[0].k_val < self.kdj_list_4h[1].k_val) \
                and (self.kdj_list_4h[0].j_val < self.kdj_list_4h[1].j_val):
            check_kdj_4h_signal = True
        else:
            check_kdj_4h_signal = False
        all_signals_dict["check_kdj_4h_signal"] = check_kdj_4h_signal
        self.prompt_text += f"\n 当前在4小时周期的KDJ的最新K值小于前K值且最新J值小于前J值为 {check_kdj_4h_signal}。"

        if self._check_kdj_death_cross_by_threshold(self.kdj_list_1h, self.get_dynamic_threshold()["kdj_death_cross"]):
            all_signals_dict["overbought_death_cross_signal"] = True
            self.prompt_text += f"\n 当前在1小时周期的KDJ刚形成高位(80)死叉位置。"

        check_fng_signal = self.get_fng_signal(buy=False)
        if check_fng_signal is not None:
            all_signals_dict["check_fng_signal"] = check_fng_signal
            self.prompt_text += f"\n 今日的加密货币恐惧指数，卖出判断为:{check_fng_signal}。"

        if hours_diff and hours_diff >= 8:
            all_signals_dict["holding_time_too_long"] = True
            self.prompt_text += f"\n 持久时间过久，超过了8小时。"

        if any(list(all_signals_dict.values())) is not True:
            return

        signal_data = self.get_signal_count_data(*all_signals_dict.values())
        if signal_data["true_count"] == 1:
            return

        # TODO: 增加历史信号->叠加增强
        redis_client = AllCache.get_client()
        key = f"shortSignals:{self.symbol}"
        history_signals_str = redis_client.get(key)
        if history_signals_str:
            history_signals = json.loads(history_signals_str)
            history_signals_msg = f"短期累计出场次数：{len(history_signals)}"
        else:
            history_signals = {}
            history_signals_msg = ""
        history_signals[len(history_signals) + 1] = all_signals_dict
        # TODO: 过期时间是否需要叠加
        redis_client.set(key, json.dumps(history_signals), 3600)

        depth_prices_data = self.get_depth_prices(current_price)
        recommend_ask_price = depth_prices_data["recommend_ask_price"]

        direction = f" 🔴 短线高频交易(策略待优化): 📉 卖出信号, " \
                    f"<br>总体信号-<b>{signal_data['status']}</b>" \
                    f"<br>建议卖出价：{recommend_ask_price}" \
                    f"<br><br>{history_signals_msg}<br><br><br>" \
                    f"<br>总信号：{all_signals_dict}" \
                    f"<br>持仓时间：{hours_diff} 小时"

        logger.info(f"plot_gpt, _get_sell_direction_upward, sell upward, symbol:{self.symbol}"
                    f"curr 1h j_val:{self.kdj_list_1h[0].j_val}, "
                    f"curr 1h close_price:{self.kline_list_1h[0].close_price},"
                    f"curr 4h j_val:{self.kdj_list_4h[0].j_val}")
        return {"direction": direction, "current_price": current_price, "recommend_ask_price": recommend_ask_price}

    async def bull_run_strategy(self):
        """
        牛市大涨策略：
            主要工具：4小时K线图
        📈 买入信号
            4小时MACD上行：DIF上穿DEA；或者 日线MACD上行：DIF上穿DEA（多头排列或者底背离）。

            1. 从更大周期判断对当前周期段的影响：
                    1.1. 日线KDJ刚形成死叉，不再向下判断。
            2. 从更小周期判断对当前周期段的影响：
                    2.1. 1小时KDJ处于80高位死叉位置，不再向下判断。

            4. 4小时K线前2根线，处于吞没形态，不再向下判断。
            5. 4小时和1小时的双均线策略，策略因子都只有1个达标，不再向下判断。
            6. 4小时K线连续4根线KDJ的J值超100且当前段的交易量未放大，不处于FOMO阶段，不再考虑。

            7. 4小时MACD是否震荡收敛(MACD 柱状图逐步趋近 0 轴)，判断是否信号背离:
                是:
                    7.1. 最近3条的最高价逐步递增(增长率大于阀值)，初步判断趋势大涨。
                否:
                    7.1. (或)4小时KDJ最近3根线持续上行，K值大于D值。
                    7.2. (或)4小时KDJ最近3根线(不包含当前线)有金叉。
            9. 4小时k线：最近3条的最高价逐步递增(增长率大于阀值)，初步判断趋势大涨。

            增加辅助信号：日线kdj金叉位置

            若不触发当前报警 且未触发信号背离：
                则判断：24小时内有历史报警+当前价格大于历史20根线的最高价，触发报警
        """
        self.prompt_text += "输出买入的建议概率。"
        if self.macd_list_1d[0].macd < 0 and self.macd_list_4h[0].macd < 0:
            return
        self.prompt_text += f"\n<br> 1.先判断大周期行情： 当前日线的MACD大于0为 {self.macd_list_1d[0].macd > 0}，当前4小时线的MACD大于0为 {self.macd_list_4h[0].macd > 0}。"
        if self._check_trade_interval_time() is False:
            return
        if await self.has_limit_price_check((0, 1, 3)):
            return

        kdj_1d_strategies = KdjStrategy(self.kdj_list_1d)
        if kdj_1d_strategies.get_curr_death_cross():
            return
        self.prompt_text += f"\n<br> 2. 再判断当前是否处于特殊信号：当前日线的KDJ没有刚形成死叉。"

        kdj_1h_strategies = KdjStrategy(self.kdj_list_1h)
        if kdj_1h_strategies.get_curr_death_cross_by_threshold(Decimal("80")):
            return
        self.prompt_text += f"\n 当前1小时线KDJ不处于80高位死叉位置。"

        kline_4h_strategies = CandlestickStrategy(self.kline_list_4h, self.macd_list_4h)
        if kline_4h_strategies.get_engulfing_pattern_strategy(window_index=1)["has_bearish_engulfing"] is True:
            return
        self.prompt_text += f"\n 当前4小时线的前2根线(不包含当前根线)，不处于看跌吞没状态。"

        ema_4h_strategy = kline_4h_strategies.get_ema_strategy(is_bid=True)
        kline_1h_strategies = CandlestickStrategy(self.kline_list_1h, self.macd_list_1h)
        ema_1h_strategy = kline_1h_strategies.get_ema_strategy(is_bid=True)
        if sum(ema_4h_strategy.values()) <= 1 and sum(ema_1h_strategy.values()) <= 1:
            return
        self.prompt_text += f"\n 4小时ema策略：{ema_4h_strategy}。"
        self.prompt_text += f"\n 1小时ema策略：{ema_1h_strategy}。"

        val_4h_strategy = kline_4h_strategies.get_vol_strategy(5)
        kdj_4h_strategies = KdjStrategy(self.kdj_list_4h)
        has_kdj_extreme_increase = kdj_4h_strategies.get_extreme_increase(4)
        if has_kdj_extreme_increase and not val_4h_strategy.get("has_enhance_spike_volume", False):
            return
        self.prompt_text += f"\n 4小时KDJ的J值连续超100为 {has_kdj_extreme_increase}。"
        self.prompt_text += f"\n 4小时线的当前交易大于过去5根线交易量均值的1.3b倍为 {val_4h_strategy.get('has_enhance_spike_volume', False)}。"

        direction = ""
        current_price = self.kline_list_1h[0].close_price
        ignore_kdj_signal = False

        # 4小时MACD(不包含当前线)趋近死叉). 设置小窗口值为3, 拟合计算相对趋势. 斜率绝对值<0.001时, 判断趋于0.
        # TODO: 斜率值需要回测调整。斜率绝对值<0.002时, 判断趋于0
        current_trend_macd_4h = enhanced_analyze_list_trend_by_groups(
            [i.macd for i in self.macd_list_4h[1:19]][::-1], group_size=3)

        if current_trend_macd_4h["trend"] in ["downward_spiral", "modest_decline"] \
                and abs(current_trend_macd_4h["slope"]) < Decimal("0.002"):
            # 触发信号背离, KDJ失效
            logger.info(f"plot_gpt, bull_run_strategy, symbol:{self.symbol}, trend_info:{current_trend_macd_4h}")

            # 趋势已确立的行情：如果MACD已经明确表明趋势方向（如DIF和DEA持续分离），则KDJ可能会在趋势中反复震荡，容易导致误判
            ignore_kdj_signal = True
            self.prompt_text += f"\n 4小时MACD(不包含当前线)趋近死叉，可能触发信号背离，kdj指标失效。"

        counter = RollingCounter(self.symbol, "BullRun")
        if ignore_kdj_signal:
            final_count = counter.get_last_count()

            max_price = kline_1h_strategies.get_donchian_channel()["max_price"]
            if current_price >= max_price and final_count > 0:
                direction += f"<br>当前价破新高 <br>24小时内🐮次数: {final_count}"
                # 1小时时间
                open_ts = self.kline_list_1h[0].open_ts
                self.prompt_text += f"\n<br> 3. 最后判断更精细的因子：当前价格突破了1小时线的最近6根线的最高价。"
            else:
                return

        else:
            kdj_4h_up_signal = kdj_4h_strategies.get_uptrend(3)
            kdj_4h_cross_signal = kdj_4h_strategies.get_history_golden_cross_count(4)

            if any([kdj_4h_up_signal, kdj_4h_cross_signal]) is not True:
                return
            self.prompt_text += f"\n<br> 3. 最后判断更精细的因子： 4小时KDJ最近3根线持续上行为：{kdj_4h_up_signal}。"
            self.prompt_text += f"\n 4小时KDJ最近3根线(不包含当前线)有金叉为: {kdj_4h_cross_signal}。"

            high_price_up_4h_signal = self._check_increasing_highs(self.kline_list_4h[:3])
            open_ts = self.kline_list_1h[0].open_ts

        if self._check_kdj_golden_cross_by_threshold(self.kdj_list_1d, Decimal("40")):
            direction += "信号增强：日线KDJ金叉"
            self.prompt_text += f"\n 当前日线KDJ刚形成40以下的低位金叉位置。"

        depth_prices_data = self.get_depth_prices(current_price)
        depth_bid_price = depth_prices_data["bid_price"]
        depth_ask_price = depth_prices_data["ask_price"]
        recommend_bid_price = depth_prices_data["recommend_bid_price"]

        bb_upper_4h, bb_lower_4h = self.get_bollinger_bands("4h")

        tp_and_sl_price_data = self.get_tp_and_sl(current_price, depth_bid_price, depth_ask_price, bb_upper_4h)
        tp_price = tp_and_sl_price_data["atr_tp_price"]
        sl_price = tp_and_sl_price_data["atr_sl_price"]

        direction += f"""
        <br>建议买入价: {recommend_bid_price}
        <br><br><br>
        """

        if self.symbol in TMP_STAR_TOP10:
            direction += "<br>🌟 🌟 🌟 🌟 🌟 </br>"

        direction += self.prompt_text

        logger.info(f"plot_gpt, bull_run_strategy, symbol:{self.symbol}, "
                    f"curr_k_4h:{self.kdj_list_4h[0].k_val}, curr_d_4h:{self.kdj_list_4h[0].d_val}, "
                    f"curr_k_1h:{self.kdj_list_1h[0].k_val}, curr_d_1h:{self.kdj_list_1h[0].d_val}, "
                    f"curr_j_1h:{self.kdj_list_1h[0].j_val}")

        await BackTestHandler(self.symbol).add_bid_ticket(
            current_price,
            recommend_bid_price,
            self.check_time,
            4,
            direction
        )

        email_msg_md5_str = f"plotGpt:bull_run_strategy:{self.symbol}:{open_ts}"
        email_msg_md5 = hashlib.md5(email_msg_md5_str.encode("utf8")).hexdigest()

        try:
            return await EmailMsgHistoryTable.aio_get(EmailMsgHistoryTable.msg_md5 == email_msg_md5)
        except EmailMsgHistoryTable.DoesNotExist:
            counter.increment()

        close_monitor_url = f"{INNER_GET_DELETE_LIMIT_PRICE_URL}{self.symbol}"
        set_limit_price_url = f"{INNER_GET_SUBMIT_LIMIT_PRICE_URL}?" \
                              f"symbol={self.symbol}&low_price={sl_price}" \
                              f"&high_price={tp_price}"

        self.result[self.symbol] = self.bull_run_strategy_reformat_notice(
            direction, open_ts, current_price, self.check_time, close_monitor_url, set_limit_price_url)

        email_content = "".join(self.result.values())
        await EmailMsgHistoryTable.aio_create(msg_md5=email_msg_md5, msg_content=email_content)

        logger.info(
            f"PlotGptHandle.bull_run_strategy finish, start end_msg, symbol:{self.symbol}, ts:{self.check_time}")
        await self.send_msg(self.email_title, email_content)

    async def get_buy_score_info(self, current_price):
        # if self.macd_list_1d[0].macd < 0 and self.macd_list_4h[0].macd < 0:
        #     return

        score_info = {}

        # 趋势因子(40分)
        kline_4h_strategies = CandlestickStrategy(self.kline_list_4h, self.macd_list_4h)
        ema_4h_strategy = kline_4h_strategies.get_ema_strategy(is_bid=True)
        if ema_4h_strategy.get("has_ema_stack"):
            score_info["4h_has_ema_stack"] = 10 # 4 小时 EMA12 > EMA26（current_EMA12 > current_EMA26 多头排列） → +10 分 *（趋势核心）*

        bb_4h_info = kline_4h_strategies.get_bollinger_bands()
        if ema_4h_strategy.get("has_ema_uptrend"):
            score_info["4h_has_ema_uptrend"] = self._get_adjust_score_4h_has_ema_uptrend(
                5, current_price, self.kline_list_4h[0].high_price, self.kline_list_4h[0].open_price, bb_4h_info
            ) # 4 小时 EMA12 上升（current_EMA12 > prev_EMA12） → +5 分

        kline_1h_strategies = CandlestickStrategy(self.kline_list_1h, self.macd_list_1h)
        ema_1h_strategy = kline_1h_strategies.get_ema_strategy(is_bid=True)
        if ema_1h_strategy.get("has_ema_stack"):
            score_info["1h_has_ema_stack"] = 5 # 1 小时 EMA12 > EMA26（current_EMA12 > current_EMA2 多头排列） → +5 分 *（短期趋势确认）*

        prev_ema_trend_1h_info = kline_1h_strategies.get_prev_ema_trend_strategy()
        if prev_ema_trend_1h_info["trend"] in ["parabolic_move", "modest_increase"]:
            score_info["1h_has_prev_ema_uptrend"] = 5 # 1 小时 EMA12 上升（EMA12 斜率 > 0） → +5 分

        macd_1h_strategies = MacdStrategy(self.macd_list_1h)
        prev_macd_trend_1h_info = macd_1h_strategies.get_prev_trend_strategy()
        if prev_macd_trend_1h_info["trend"] in ["parabolic_move", "modest_increase"]:
            score_info["1h_has_prev_macd_uptrend"] = 5 # 1 小时 MACD 上升 → +5 分

        if self.macd_list_1d[0].macd > 0:
            score_info["macd_1d>0"] = 5 # 日线 MACD > 0 → +5 分

        if self.macd_list_4h[0].macd > 0:
            score_info["macd_4h>0"] = 5 # 4 小时 MACD > 0 → +5 分

        # 短期动能因子(30分)
        kdj_4h_strategies = KdjStrategy(self.kdj_list_4h)
        if kdj_4h_strategies.get_uptrend(3):
            score_info["kdj_4h_up"] = self._get_adjust_score_kdj_4h_up(10) # 4 小时 KDJ 3 连升 → +10 分

        rsi_4h_strategies = RsiStrategy(self.rsi_list_4h)
        if rsi_4h_strategies.get_breakout():
            score_info["rsi_4h_breakout_60"] = 3

        if rsi_4h_strategies.get_healthy_bound():
            score_info["rsi_4h_healthy_bound_45to65"] = 3

        if rsi_4h_strategies.get_uptrend():
            score_info["rsi_4h_uptrend"] = 3

        rsi_1h_strategies = RsiStrategy(self.rsi_list_1h)
        if rsi_1h_strategies.get_rebound():
            score_info["rsi_1h_rebound_40"] = 5

        if rsi_1h_strategies.get_uptrend():
            score_info["rsi_1h_uptrend"] = 5

        if rsi_1h_strategies.get_pullback_entry():
            score_info["rsi_1h_pullback_65to60"] = 3

        kdj_1h_strategies = KdjStrategy(self.kdj_list_1h)
        kdj_1h_up_signal = kdj_1h_strategies.get_uptrend(2)
        if kdj_1h_up_signal:
            score_info["kdj_1h_up_signal"] = 5  # 1 小时 KDJ 2 连升 → +5 分

        if kdj_4h_strategies.get_curr_golden_cross():
            score_info["kdj_4h_golden_cross"] = 5 # 4 小时 KDJ 刚好处于金叉 → +5 分

        if self.kdj_list_1h[0].k_val >= self.kdj_list_1h[0].d_val:
            score_info["kdj_1h_no_death_cross"] = \
                self._get_adjust_score_kdj_1h_no_death_cross(5, kdj_1h_strategies) # 1 小时 KDJ 没死叉 → +5 分

        # 成交量因子(20分)
        vol_4h_5_strategy = kline_4h_strategies.get_vol_strategy(5)
        vol_4h_10_strategy = kline_4h_strategies.get_vol_strategy(10)
        if vol_4h_5_strategy.get("has_spike_volume") and vol_4h_10_strategy.get("has_spike_volume"):
            score_info["vol_4h_continue_up"] = 10 # 4 小时成交量 > 5 根均值 且 > 10 根均值 → +10 分

        vol_1h_strategy = kline_1h_strategies.get_vol_strategy(5)
        if vol_1h_strategy.get("has_enhance_spike_volume"):
            score_info["vol_1h_up_1.3x"] = 5 # 1 小时成交量 > 5 根均值 * 1.3 → +5 分

        if vol_4h_5_strategy.get("has_spike_volume") and vol_1h_strategy.get("has_spike_volume"):
            score_info["vol_4h_1h_up"] = 5 # 4 小时成交量 > 5 根均值 且 1 小时成交量 > 5 根均值 → +5 分

        # 支持阻力因子(10分)
        kline_1h_strategies = CandlestickStrategy(self.kline_list_1h, self.macd_list_1h)
        bb_info = kline_1h_strategies.get_bollinger_bands()
        bb_upper_price = bb_info["bb_upper"]
        bb_lower_price = bb_info["bb_lower"]
        bb_mid_price = bb_info["bb_mid"]
        logger.info(f"plot_gpt get_buy_score_info check bb, symbol:{self.symbol}, current_price:{current_price}, bb_info:{bb_info}")
        if bb_mid_price <= current_price < bb_upper_price:
            near_info = check_near_low(self.kline_list_1h[:21][::-1], bb_mid_price, bb_upper_price, logger)
        elif bb_lower_price <= current_price < bb_mid_price:
            near_info = check_near_low(self.kline_list_1h[:21][::-1], bb_lower_price, bb_mid_price, logger)
        else:
            near_info = None

        if near_info and near_info["is_near"]:
            score_info["1h_low_price_near_support"] = 5 # 1小时最低价靠近支撑位 -> +5 分
        if near_info and near_info["price_structure_valid"]:
            score_info["1h_low_price_resistance_range"] = 5 # 1小时最低价处于阻力区间内 -> +5 分

        sum_score = sum(score_info.values())
        if sum_score >= 40:
            logger.info(f"plot_gpt get_buy_score_info finish, symbol:{self.symbol}, score:{sum_score}, bb_info:{bb_info}")
        if sum_score >= 60:
            return score_info
        return

    def _get_adjust_score_kdj_1h_no_death_cross(self, score, kdj_1h_strategies):
        """
        过去 5 根 K 线的 KDJ 形态 - 判断 - kdj_1h_no_death_cross 分值
        5 根 K 线中 2 次金叉 + 2 次死叉 - 震荡行情，趋势不明朗 - 0 分
        5 根 K 线中 1 次金叉 + 1 次死叉 - 轻微震荡，可能仍有趋势 - 2 分
        5 根 K 线中 只出现 1 次金叉，之后一直维持 - 趋势稳定 - 5 分

        rsi > 70 -> -3 分
        """
        # TODO: 根据描述优化
        if kdj_1h_strategies.get_sideways():
            score -= 2 # KDJ 处于震荡状态 -> -2 分

        if self.rsi_list_1h.rsi > Decimal("70"):
            score -= 2 # RSI>70 -> -2 分

        return score

    def _get_adjust_score_kdj_4h_up(self, score):
        """
        95 < J ≤ 100	按比例递减，如 10 - (J-95) * 1
        """
        curr_j = self.kdj_list_4h[0].j_val
        if Decimal("20") < curr_j <= Decimal("95"):
            return score # 20<J<=95 -> 不扣分
        elif Decimal("95") < curr_j <= Decimal("100"):
            diff = (curr_j - Decimal("95")) * Decimal("1")
            return int(score - diff) # 95 < J ≤ 100 -> 按比例递减, 10 - (J-95) * 1
        elif curr_j > Decimal("100"):
            return score - 10 # J > 100 -> -10 分
        else:
            return score - 10 # J<= 20 -> -10 分

    def _get_adjust_score_4h_has_ema_uptrend(self, score, curr_price, high_price, open_price, bb_info):
        bb_upper_price = bb_info["bb_upper"]
        bb_lower_price = bb_info["bb_lower"]
        bb_mid_price = bb_info["bb_mid"]

        if curr_price < bb_lower_price:
            score += 2 # 收盘价跌破下轨 -> +2 分

        if (curr_price < bb_upper_price) and (high_price > bb_upper_price):
            score -= 3 # 最高价突破上轨但当前价低于上轨，可能是假突破 -> -3 分

        if (curr_price > bb_upper_price) and (open_price > bb_upper_price):
            score -= 3 # 开盘价突破上轨，当前价突破上轨，高开高走 -> -3 分
        return score
