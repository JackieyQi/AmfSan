#! /usr/bin/env python
# -*- coding: UTF-8 -*-

import logging
from decimal import Decimal
from utils.common import decimal2decimal

"""
结构场景 + 条件链判断
"""

"""
"""
# TODO:可以考虑“评分走势”的平滑机制
"""
TODO: 可以考虑“评分走势”的平滑机制
取消「即时分数」，也就是当前K线满足条件就加分，其实可以进一步强化稳定性，比如：
    额外思路：
    用滑动窗口打分：近3根K线的得分平均 > 60，再考虑买入。
    或者 评分突然从 <50 跳到 >70，说明趋势刚启动，作为额外信号。
"""

logger = logging.getLogger(__name__)


class ModeExcludeFactor:
    @staticmethod
    def has_bearish(kline_4h_factors, macd_4h_factors):
        is_4h_ema12_continue_down = kline_4h_factors.is_ema12_continue_down(window_size=3)
        is_4h_macd_death_cross = any([macd_4h_factors.is_death_cross(index=i) for i in range(2)])

        if (is_4h_ema12_continue_down or is_4h_macd_death_cross) and kline_4h_factors.is_bearish_engulfing_k():
            return True

        return False


class ModelBollMidRebound(object):
    def __init__(self, curr_price):
        self.name = "model_boll_mid_rebound"
        self.name_str = "强趋势上升，布林带中轨反弹结构"
        self.curr_price = curr_price
        self.score = 0

    def get_recommend_price(self, curr_low_price):
        recommend_bid_price = (self.curr_price + curr_low_price) / Decimal("2")
        return {
            "recommend_bid_price": decimal2decimal(recommend_bid_price)
        }

    def is_detected(
            self, kline_4h_factors, kline_1h_factors, macd_4h_factors, kdj_1h_factors, rsi_1h_factors):
        if ModeExcludeFactor.has_bearish(kline_4h_factors, macd_4h_factors):
            return False

        # 前置条件：4小时多头排列+4小时的EMA12和EMA26连续上升趋势+4小时MACD没有连续递减
        if kline_4h_factors.is_ema_bullish_stack(window_size=5) \
                and kline_4h_factors.is_ema12_continue_up(window_size=5) \
                and kline_4h_factors.is_ema26_continue_up(window_size=5) \
                and not macd_4h_factors.is_continue_down():
            self.score += 10

            # 条件A：当前最低价跌破中轨，收盘价回到中轨上方
            is_4h_structure = kline_4h_factors.get_fake_breakdown_by_bb(index=0, is_low=False)
            if is_4h_structure:
                self.score += 15

            is_1h_structure = kline_1h_factors.get_fake_breakdown_by_bb(index=0, is_low=False)
            if is_1h_structure:
                self.score += 10

            if is_4h_structure or is_1h_structure:

                # 子因子A1：1小时的KDJ的J底部背离
                is_new_low_price = kline_1h_factors.is_new_low_price(3)
                if kdj_1h_factors.is_j_bullish_divergence(is_new_low_price):
                    self.score += 5

                # 子因子A2：1小时的RSI从低位反弹
                for i in range(3):
                    if rsi_1h_factors.get_breakout_from_low(index=i):
                        self.score += 5
                        break

        return self.score >= 22.5  # 大于总分的1/2


class ModelBollLowReboundBullishSideways(object):
    def __init__(self, curr_price):
        self.name = "model_boll_low_rebound_bullish_sideways"
        self.name_str = "4小时多头排列+震荡，1小时布林带下轨反弹结构"
        self.curr_price = curr_price
        self.score = 0

    def get_recommend_price(self, kline_list_1h, bb_list_1h):
        if kline_list_1h[0].high_price > (bb_list_1h[0].bblower + bb_list_1h[0].bbmid)/Decimal("2"):
            recommend_bid_price = None
        else:
            recommend_bid_price = self.curr_price
        return {
            "recommend_bid_price": recommend_bid_price
        }

    def is_detected(self, kline_4h_factors, kline_1h_factors, macd_4h_factors, kdj_1h_factors, rsi_1h_factors):
        if ModeExcludeFactor.has_bearish(kline_4h_factors, macd_4h_factors):
            return False

        # 前置条件：更大周期的4小时的EMA多头排列+4小时的EMA12最近5根没有连续下降
        if kline_4h_factors.is_ema_bullish_stack(window_size=5) \
                and not kline_4h_factors.is_ema12_continue_down(window_size=5):
            self.score += 10

            # 条件B：前k线的最低价跌破下轨，收盘价回到下轨上方
            is_1h_structure = kline_1h_factors.get_fake_breakdown_by_bb(index=1, is_low=True)
            if is_1h_structure:
                self.score += 10

                # 子因子B1：反弹K线结构:前k线长下影阳线
                if kline_1h_factors.is_bullish_k() \
                        and kline_1h_factors.is_long_lower_shadow_k(index=1, scale=Decimal("2")):
                    self.score += 5

                # 子因子B2：1小时的KDJ的J底部背离
                is_new_low_price = kline_1h_factors.is_new_low_price(3, index=1)
                if kdj_1h_factors.is_j_bullish_divergence(is_new_low_price, index=1, j_threshold=Decimal("10")):
                    self.score += 5

                # 子因子B3： 1小时 RSI-6 低于20(短期超卖)且反弹
                if rsi_1h_factors.get_rebound(index=1, threshold=Decimal("20")):
                    self.score += 5

                # 子因子B4：成交量放大: volume > vol_ma * 1.5

        return self.score >= 25  # 任一子因子满足


class ModelBollLowReboundBullishDown(object):
    def __init__(self, curr_price):
        self.name = "model_boll_low_rebound_bullish_Down"
        self.name_str = "多头排列+下跌，布林带下轨反弹结构"
        self.curr_price = curr_price
        self.score = 0

    def get_recommend_price(self, kline_1h_factors):
        if kline_1h_factors.is_along_lower_band(n=7):
            recommend_bid_price = None
        else:
            recommend_bid_price = self.curr_price
        return {
            "recommend_bid_price": recommend_bid_price
        }

    def is_detected(self, kline_4h_factors, kline_1h_factors, macd_4h_factors, kdj_1h_factors, rsi_1h_factors):
        if ModeExcludeFactor.has_bearish(kline_4h_factors, macd_4h_factors):
            return False

        # 前置条件：更大周期的4小时的EMA多头排列+4小时的EMA12最近5根连续下降+4小时附近没有收盘价跌破下轨
        if kline_4h_factors.is_ema_bullish_stack(window_size=5) \
                and kline_4h_factors.is_ema12_continue_down(window_size=5) \
                and not kline_4h_factors.is_breakdown_by_bb(window_size=5):
            self.score += 10

            # 条件C：前4根线至少3根线击破下轨且收盘价反弹+当前最低价跌破下轨，收盘价回到下轨上方
            window_size = 4
            fake_list = [kline_1h_factors.get_fake_breakdown_by_bb(index=i, is_low=True) for i in range(4)]
            is_1h_structure = sum(fake_list) > (window_size/2)
            if is_1h_structure:
                self.score += 10

                # 子因子C1：反弹K线结构:长下影阳线
                if kline_1h_factors.is_bullish_k() and kline_1h_factors.is_long_lower_shadow_k(scale=Decimal("2")):
                    self.score += 5

                # 子因子C2：反弹K线结构:看涨吞没
                if kline_1h_factors.is_bullish_engulfing_k():
                    self.score += 5

                # 子因子C3： 1小时 RSI-6 低于35(短期超卖)且反弹
                if rsi_1h_factors.get_rebound(threshold=Decimal("35")):
                    self.score += 5

        return self.score >= 25  # 任一子因子满足


class ModelLTypeRebound(object):
    def __init__(self, curr_price):
        self.name = "model_l_type_rebound"
        self.name_str = "日线EMA多头+4小时布林带形成L形状，1小时布林带下轨反弹结构"
        self.curr_price = curr_price
        self.score = 0

    def get_recommend_price(self, bb_list_1h):
        return {
            "recommend_bid_price": bb_list_1h.bblower,
        }

    def is_detected(self, kline_1d_factors, kline_4h_factors, kline_1h_factors, macd_4h_factors, kdj_1h_factors):
        if ModeExcludeFactor.has_bearish(kline_4h_factors, macd_4h_factors):
            return False

        # 前置条件：更大周期的日线的EMA多头排列+4小时布林带形成L形状
        if kline_1d_factors.is_ema_bullish_stack(window_size=5) \
                and kline_4h_factors.has_l_shape():
            self.score += 10

            # 条件D：当前k线的最低价跌破下轨，收盘价回到下轨上方
            is_1h_structure = kline_1h_factors.get_fake_breakdown_by_bb(index=0, is_low=True)
            if is_1h_structure:
                self.score += 10

                # 子因子D1：1小时的KDJ的J底部背离
                is_new_low_price = kline_1h_factors.is_new_low_price(3, index=1)
                if kdj_1h_factors.is_j_bullish_divergence(is_new_low_price, index=1, j_threshold=Decimal("10")):
                    self.score += 5

        # TODO:
        return self.score >= 20  # 任一子因子满足


class ModelWTypeRebound(object):
    """
    结构判断：
        定义时间窗 window_size=15（蜡烛图长度）：
            P1：找到过去15根内最低点（第一个低点）；
            P2：在 P1 后蜡烛内找到中间高点；
            P3：P2 后内再出现次低点，价格接近 P1，且不明显创新低
    """
    def __init__(self, curr_price):
        self.name = "model_w_type_rebound"
        self.name_str = "日线EMA多头+4小时布林带形成L形状，1小时布林带下轨反弹结构"
        self.curr_price = curr_price
        self.score = 0

    def get_recommend_price(self, bb_list_1h):
        return {
            "recommend_bid_price": self.curr_price,
        }

    def is_detected(self, kline_list_1h, bb_list_1h, rsi_list_1h, kline_4h_factors, kline_1h_factors, macd_4h_factors):
        if ModeExcludeFactor.has_bearish(kline_4h_factors, macd_4h_factors):
            return False

        window_size = 15
        low_prices_list = [i.low_price for i in kline_list_1h[:window_size]]
        p1_price = min(low_prices_list)
        p1_index = low_prices_list.index(p1_price)
        if p1_index == 0 or p1_index == 14:
            return False

        # p1前部分沿下轨/TODO:快速下落
        if not (kline_1h_factors.is_along_lower_band(index=p1_index, n=window_size-p1_index)
                or (
                        kline_list_1h[window_size-1].open_price > (bb_list_1h[window_size-1].bbupper + bb_list_1h[window_size-1].bbmid)/Decimal("2")
                        and p1_price < (bb_list_1h[p1_index].bbmid + bb_list_1h[p1_index].bblower)/Decimal("2")
                )
        ):
            return False

        high_prices_list = [i.high_price for i in kline_list_1h[:p1_index]]
        if not high_prices_list:
            return False
        p2_price = max(high_prices_list)
        p2_index = high_prices_list.index(p2_price)
        # p2中间高点超过布林带中轨
        if not (bb_list_1h[p2_index].bbmid < p2_index < (bb_list_1h[p2_index].bbmid + bb_list_1h[p2_index].bbupper)/Decimal("2")):
            return False

        low_prices_list = [i.low_price for i in kline_list_1h[:p2_index]]
        if not low_prices_list:
            return False
        p3_price = max(low_prices_list)
        p3_index = low_prices_list.index(p3_price)

        if not (p3_price >= p1_price * Decimal("0.97")):
            return False

        if p3_index != 1:
            return False

        # 上面逻辑：价格结构满足 P1-P2-P3 的模式

        # 子因子W1：RSI 增强, RSI(P3) > RSI(P1)
        if rsi_list_1h[p3_index].rsi > rsi_list_1h[p1_index].rsi:
            self.score += 5

        # 子因子W2：成交量增加, vol(P3) > 1.5 * avg_vol
        # 子因子W3：MACD 金叉 / 柱体翻红	DIF>DEA 且 MACD>0

        return self.score >= 5
