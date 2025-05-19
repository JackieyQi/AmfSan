#! /usr/bin/env python
# -*- coding: UTF-8 -*-

import logging
import numpy as np
from typing import Optional
from decimal import Decimal
from dataclasses import dataclass
from utils.common import decimal2decimal

from .factor import CandlestickFactor, MacdFactor, KdjFactor, RsiFactor

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


@dataclass
class ModelBase:
    kline_1d_factors: Optional[CandlestickFactor] = None
    kline_4h_factors: Optional[CandlestickFactor] = None
    kline_1h_factors: Optional[CandlestickFactor] = None
    kline_15m_factors: Optional[CandlestickFactor] = None
    
    macd_4h_factors: Optional[MacdFactor] = None
    macd_1h_factors: Optional[MacdFactor] = None
    macd_15m_factors: Optional[MacdFactor] = None
    
    kdj_4h_factors: Optional[KdjFactor] = None
    kdj_1h_factors: Optional[KdjFactor] = None
    kdj_15m_factors: Optional[KdjFactor] = None
    
    rsi_4h_factors: Optional[RsiFactor] = None
    rsi_1h_factors: Optional[RsiFactor] = None
    rsi_15m_factors: Optional[RsiFactor] = None
    
    def has_bearish_1h(self):
        is_4h_ema12_continue_down = self.kline_4h_factors.is_ema12_continue_down(window_size=3)
        
        if self.macd_4h_factors.is_death_cross(index=0):
            is_4h_macd_death_cross = True
            death_cross_4h_index = 1
        elif self.macd_4h_factors.is_death_cross(index=1):
            is_4h_macd_death_cross = True
            death_cross_4h_index = 2
        else:
            is_4h_macd_death_cross = False
            death_cross_4h_index = None
            
        if (is_4h_ema12_continue_down or is_4h_macd_death_cross) and self.kline_4h_factors.is_bearish_engulfing_k():
            return True
        
        if is_4h_macd_death_cross and self.macd_4h_factors.is_bullish_stack(index=death_cross_4h_index):
            return True
        
        # 4小时: MACD<0 且柱下降; KDJ 死叉且加速下行
        is_4h_macd_bearish = self.macd_4h_factors.macd_list[0].macd < 0 and self.macd_4h_factors.is_continue_down(
            index=1)
        is_4h_kdj_bearish = (self.kdj_4h_factors.kdj_list[0].k_val < self.kdj_4h_factors.kdj_list[0].d_val) and (
            self.kdj_4h_factors.is_j_continue_down(index=1))
        if is_4h_macd_bearish and is_4h_kdj_bearish:
            return True
        
        # 1小时:
        if self.macd_1h_factors.is_death_cross(index=0):
            is_1h_macd_death_cross = True
            death_cross_1h_index = 1
        elif self.macd_1h_factors.is_death_cross(index=1):
            is_1h_macd_death_cross = True
            death_cross_1h_index = 2
        else:
            is_1h_macd_death_cross = False
            death_cross_1h_index = None
        
        if is_1h_macd_death_cross and self.macd_1h_factors.is_bullish_stack(index=death_cross_1h_index):
            return True
        
        # 15分钟：
        if self.macd_15m_factors.is_death_cross(index=0):
            is_15m_macd_death_cross = True
            death_cross_15m_index = 1
        elif self.macd_15m_factors.is_death_cross(index=1):
            is_15m_macd_death_cross = True
            death_cross_15m_index = 2
        else:
            is_15m_macd_death_cross = False
            death_cross_15m_index = None
        
        if is_15m_macd_death_cross and self.macd_15m_factors.is_bullish_stack(index=death_cross_15m_index, window_size=3):
            return True
        
        return False
    
    def has_bearish_4h(self):
        # 当前价格偏离上轨不超过X%
        if any([self.kline_4h_factors.is_curr_price_away_from_bbupper(index=i) for i in range(2)]):
            return True
        
        return False


class ModelTopRise(ModelBase):
    """
    4小时波段交易: 布林贴顶加速上涨模型(贴顶上涨)(主升浪):
            结构节奏：几乎无回调，连续阳线
            入场逻辑：强势追涨（跟随）
            风控点位：前一小时K线最低点或短EMA线
            策略属性：趋势追踪
            出现场景：强力突破、主升浪中段
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        self.name = "model_top_rise"
        self.name_str = "布林贴顶加速上涨模型"
        self.score = 0

        self.curr_price = self.kline_1h_factors.kline_list[0].close_price if self.kline_1h_factors else None
        self.recommend_bid_price = None
        self.recommend_ask_price = None
        self.recommend_sl_price = None
        self.recommend_tp_price = None

    def cal_recommend_price(self):
        self.recommend_bid_price = self.curr_price
        
        self.recommend_ask_price = self.curr_price

    def is_in(self):
        if self.has_bearish_4h():
            return False

        # 大时间周期: ema多头排列
        if self.kline_1d_factors.is_ema_bullish_stack(window_size=1):
        
            # 当前时间周期: {window_size} 根k线的阳线比例 >= 70%
            window_size = 4
            count_1h_bullish_k = [self.kline_4h_factors.is_bullish_k(index=i) for i in range(1, 1+window_size)]
            is_bullish_k = sum(count_1h_bullish_k) >= window_size * 0.7

            # 当前时间周期: 至少连续 {window_size} 根K线收盘价 > EMA12
            window_size = 3
            is_bullish_ema12 = self.kline_4h_factors.is_ema12_continue_lt_close(index=1, window_size=window_size)

            # 当前时间周期: 连续 {window_size} 根以上K线收于布林带上轨上方或贴近上轨
            window_size = 3
            tolerance = Decimal("0.3")
            count_4h_close_gt_bbupper = [self.kline_4h_factors.is_near_upper(
                index=i, tolerance=tolerance) for i in range(1, 1+window_size)]
            is_bullish_boll = sum(count_4h_close_gt_bbupper) >= window_size
            
            if sum([is_bullish_k, is_bullish_ema12, is_bullish_boll]) >= 3:
                # 小周期: 具体入场点
                # 小周期: 连续3根阳线
                count_1h_bullish_k = [self.kline_1h_factors.is_bullish_k(index=i) for i in range(3)]
                is_bullish_k = sum(count_1h_bullish_k) >= 3

                # 小周期: 至少连续3根K线收于布林带上轨上方或贴近上轨
                is_bullish_boll = self.kline_1h_factors.is_along_upper_band(n=3)
                
                if sum([is_bullish_k, is_bullish_boll]) >= 1:
                    return True
                
        return False
    
    def is_in_twice(self):
        """
        短期盘整后, 二次进入
        """
        if self.has_bearish_4h():
            return False
        
        # 当前价格突破前高
        if self.kline_4h_factors.is_new_high_price(20, index=0):
            # 盘整区间不超过 {window_size} 根K线
            window_size = 10
            is_in_range = any([self.kline_4h_factors.is_near_upper(index=i) for i in range(window_size)])
            if is_in_range:
                # 小周期: 放量突破（当前K线量 > 近10根均量 1.5倍）
                is_vol = False
                vol_1h = self.kline_1h_factors.get_vol_factor(10, index=0, rate_threshold=Decimal("1.5"))
                if "has_enhance_spike_volume" in vol_1h and vol_1h["has_enhance_spike_volume"]:
                    is_vol = True
                else:
                    vol_1h = self.kline_1h_factors.get_vol_factor(10, index=1, rate_threshold=Decimal("1.5"))
                    if "has_enhance_spike_volume" in vol_1h and vol_1h["has_enhance_spike_volume"]:
                        is_vol = True
                
                # 小周期: macd柱体放大
                is_macd_continue_up = self.macd_1h_factors.is_continue_up(window_size=5)
                if is_macd_continue_up and vol_1h["has_spike_volume"]:
                    is_macd = True
                else:
                    is_macd = False
                
                # 小周期: RSI突破 60 并继续走高  
                if self.rsi_1h_factors.rsi_list[0].rsi > Decimal("70") and self.rsi_1h_factors.get_breakout():
                    is_rsi = True
                else:
                    is_rsi = False
                    
                if any([is_vol, is_macd, is_rsi]):
                    return True

        return False
    
    def is_out(self):
        # 当前时间周期: MACD柱体连续缩短
        is_macd_bullish = self.macd_4h_factors.is_continue_down(index=0)
        # 当前时间周期: KDJ 死叉 + J值钝化
        is_kdj_death_cross = any([self.kdj_4h_factors.is_death_cross(index=i) for i in range(2)])
        is_kdj_j_downtrend = self.kdj_4h_factors.is_j_continue_down(index=0, window_size=2) and \
            self.kdj_4h_factors.kdj_list[0].j_val < Decimal("70")
        is_kdj_bullish = all([is_kdj_death_cross, is_kdj_j_downtrend])
        # 当前时间周期: RSI快速跌破70或60
        is_rsi_bullish = any([self.rsi_4h_factors.is_fast_down(index=i) for i in range(2)]) and \
            self.rsi_4h_factors.rsi_list[0].rsi < 70
        
        # 主趋势减弱
        if sum([is_macd_bullish, is_kdj_bullish, is_rsi_bullish]) >= 2:
            
            # 当前时间周期: k线出现看跌吞没
            is_bearish_engulfing_k = any([self.kline_4h_factors.is_bearish_engulfing_k(index=i) for i in range(2)])
            # 当前时间周期: 当前K线最高价远离布林带上轨+RSI > 85
            is_away = any([self.kline_4h_factors.is_high_price_away_from_bbupper(index=i) for i in range(2)])
            is_rsi_gt_85 = any([self.rsi_4h_factors.rsi_list[i].rsi > 85 for i in range(2)])
            # 当前时间周期: kdj出场死叉
            is_kdj = any([self.kdj_4h_factors.is_death_cross(index=i) for i in range(2)])
            
            # 价格行为触发
            if is_bearish_engulfing_k or (is_away and is_rsi_gt_85) or is_kdj:
                
                # 小周期
                # 1小时EMA12死叉EMA26
                # RSI在1小时级别下穿60 + MACD跌破0
                # 高位横盘3根以上K线后跌破布林中轨
                # TODO:
                return True
        return False


class ModelOscillation(ModelBase):
    """
    4小时波段交易: 震荡模型
        : 震荡突破 ≠ 一定趋势启动
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        self.name = "model_oscillation"
        self.name_str = "4小时波段交易: 震荡模型"
        self.score = 0

        self.curr_price = self.kline_1h_factors.kline_list[0].close_price if self.kline_1h_factors else None
        self.recommend_bid_price = None
        self.recommend_ask_price = None
        self.recommend_sl_price = None
        self.recommend_tp_price = None
        
    def is_in(self):
        # k线 实体小、方向混乱、多影线、收敛形态
        kline_count = 0
        for i in range(5):
            if self.kline_4h_factors.is_long_upper_shadow(index=i):
                kline_count += 1
            elif self.kline_4h_factors.is_crosshairs(index=i):
                kline_count += 1
            elif self.kline_4h_factors.is_long_lower_shadow_k(index=i):
                kline_count += 1
        is_kline = kline_count >= 3
        # 价格 贴近布林带中轨
        bbmid_count = sum([self.kline_4h_factors.is_near_mid(index=i) for i in range(5)])
        is_bbmid = bbmid_count >= 3
        # macd 柱体变短 → 接近 0 附近震荡
        is_macd_downtrend = self.macd_4h_factors.is_continue_down(index=0)
        is_macd_zero = any([self.macd_4h_factors.is_near_zero(index=i) for i in range(2)])
        is_macd = is_macd_downtrend and is_macd_zero
        # rsi 没有进入过超买（>70）或超卖（<30）区间
        is_rsi = all([Decimal("30") <= self.rsi_4h_factors.rsi_list[i].rsi <= Decimal("70") for i in range(5)])

        return sum([is_kline, is_bbmid, is_macd, is_rsi]) >= 2
    
    def is_out(self):
        window_size = 20
        # 当前K线突破震荡区间高低点
        if self.kline_4h_factors.is_new_high_price(window_size, index=0):
            # 同时击穿布林带上/下轨（辅助确认）
            if self.kline_4h_factors.kline_list[0].high_price > self.kline_4h_factors.bb_list[0].bbupper:
                # TODO:放量 + 动能指标确认（MACD、KDJ）
                
                self.name += ":up"
                return True
            
        if self.kline_4h_factors.is_new_low_price(window_size, index=0):
            if self.kline_4h_factors.kline_list[0].low_price < self.kline_4h_factors.bb_list[0].bblower:
                # TODO:放量 + 动能指标确认（MACD、KDJ）
                
                self.name += ":down"
                return True

        return False


class ModelBollMidRebound(ModelBase):
    """
    |         | （中轨反弹）   |
    | 结构节奏 | 有回调→确认支撑→拉升 |
    | 入场逻辑 | 回调中寻找低吸     |
    | 风控点位 | 中轨/支撑线      |
    | 策略属性 | 回踩交易        |
    | 出现场景 | 震荡行情末端或突破初期 |

    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        self.name = "model_boll_mid_rebound"
        self.name_str = "4小时强趋势上升，1小时布林带中轨反弹结构"
        self.curr_price = self.kline_1h_factors.kline_list[0].close_price
        self.score = 0

    def get_recommend_price(self):
        curr_low_price = self.kline_1h_factors.kline_list[0].low_price
        recommend_bid_price = (self.curr_price + curr_low_price) / Decimal("2")
        return {
            "recommend_bid_price": decimal2decimal(recommend_bid_price)
        }

    def is_detected(self):
        if self.has_bearish():
            return False

        # 前置条件：4小时多头排列+4小时的EMA12和EMA26连续上升趋势+4小时MACD没有连续递减
        if self.kline_4h_factors.is_ema_bullish_stack(window_size=5) \
                and self.kline_4h_factors.is_ema12_continue_up(window_size=5) \
                and self.kline_4h_factors.is_ema26_continue_up(window_size=5) \
                and not self.macd_4h_factors.is_continue_down(index=1):
            self.score += 10

            # 条件A：当前最低价跌破中轨，收盘价回到中轨上方
            is_4h_structure = self.kline_4h_factors.get_fake_breakdown_by_bb(index=0, is_low=False)
            if is_4h_structure:
                self.score += 15

            is_1h_structure = any([self.kline_1h_factors.get_fake_breakdown_by_bb(index=i, is_low=False) for i in range(2)])
            if is_1h_structure:
                self.score += 10

            if is_4h_structure or is_1h_structure:

                # 子因子A1：1小时的KDJ的J底部背离
                is_new_low_price = self.kline_1h_factors.is_new_low_price(3)
                if self.kdj_1h_factors.is_j_bullish_divergence(is_new_low_price):
                    self.score += 5

                # 子因子A2：1小时的RSI从低位反弹
                for i in range(3):
                    if self.rsi_1h_factors.get_breakout_from_low(index=i):
                        self.score += 5
                        break

                # 子因子A3：1小时前k线为十字线，当前k线为阳线且收盘价突破中轨
                if self.kline_1h_factors.is_crosshairs(index=1) and (
                        self.kline_1h_factors.is_bullish_k(index=0)
                        and self.kline_1h_factors.kline_list[0].close_price > self.kline_1h_factors.bb_list[0].bbmid):
                    self.score += 5

        return self.score >= 22.5  # 大于总分的1/2


class ModelBollLowReboundBullishSideways(ModelBase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        self.name = "model_boll_low_rebound_bullish_sideways"
        self.name_str = "4小时多头排列+震荡，1小时布林带下轨反弹结构"
        self.curr_price = self.kline_1h_factors.kline_list[0].close_price
        self.score = 0

    def get_recommend_price(self):
        if self.kline_1h_factors.kline_list[0].high_price > (
                self.kline_1h_factors.bb_list[0].bblower + self.kline_1h_factors.bb_list[0].bbmid)/Decimal("2"):
            recommend_bid_price = None
        else:
            recommend_bid_price = self.curr_price
        return {
            "recommend_bid_price": recommend_bid_price
        }

    def is_detected(self):
        if self.has_bearish():
            return False

        # 前置条件：更大周期的4小时的EMA多头排列+4小时的EMA12最近5根没有连续下降
        if self.kline_4h_factors.is_ema_bullish_stack(window_size=5) \
                and not self.kline_4h_factors.is_ema12_continue_down(window_size=5):
            self.score += 10

            # 条件B：前k线的最低价跌破下轨，收盘价回到下轨上方
            is_1h_structure = self.kline_1h_factors.get_fake_breakdown_by_bb(index=1, is_low=True)
            if is_1h_structure:
                self.score += 10

                # 子因子B1：反弹K线结构:前k线长下影阳线
                if self.kline_1h_factors.is_bullish_k() \
                        and self.kline_1h_factors.is_long_lower_shadow_k(index=1, scale=Decimal("2")):
                    self.score += 5

                # 子因子B2：1小时的KDJ的J底部背离
                is_new_low_price = self.kline_1h_factors.is_new_low_price(3, index=1)
                if self.kdj_1h_factors.is_j_bullish_divergence(is_new_low_price, index=1, j_threshold=Decimal("10")):
                    self.score += 5

                # 子因子B3： 1小时 RSI-6 低于20(短期超卖)且反弹
                if self.rsi_1h_factors.get_rebound(index=1, threshold=Decimal("20")):
                    self.score += 5

                # 子因子B4：成交量放大: volume > vol_ma * 1.5

        return self.score >= 25  # 任一子因子满足


class ModelBollLowReboundBullishDown(ModelBase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        self.name = "model_boll_low_rebound_bullish_Down"
        self.name_str = "4小时多头排列+下跌，1小时布林带下轨反弹结构"
        self.curr_price = self.kline_1h_factors.kline_list[0].close_price
        self.score = 0

    def get_recommend_price(self):
        if self.kline_1h_factors.is_along_lower_band(n=7):
            recommend_bid_price = None
        else:
            recommend_bid_price = self.curr_price
        return {
            "recommend_bid_price": recommend_bid_price
        }

    def is_detected(self):
        if self.has_bearish():
            return False

        # 前置条件：更大周期的4小时的EMA多头排列+4小时的EMA12最近5根连续下降+4小时附近没有收盘价跌破下轨
        if self.kline_4h_factors.is_ema_bullish_stack(window_size=5) \
                and self.kline_4h_factors.is_ema12_continue_down(window_size=5) \
                and not self.kline_4h_factors.is_breakdown_by_bb(window_size=5):
            self.score += 10

            # 条件C：前4根线至少3根线击破下轨且收盘价反弹+当前最低价跌破下轨，收盘价回到下轨上方
            window_size = 4
            fake_list = [self.kline_1h_factors.get_fake_breakdown_by_bb(index=i, is_low=True) for i in range(4)]
            is_1h_structure = sum(fake_list) > (window_size/2)
            if is_1h_structure:
                self.score += 10

                # 子因子C1：反弹K线结构:长下影阳线
                if self.kline_1h_factors.is_bullish_k() and self.kline_1h_factors.is_long_lower_shadow_k(scale=Decimal("2")):
                    self.score += 5

                # 子因子C2：反弹K线结构:看涨吞没
                if self.kline_1h_factors.is_bullish_engulfing_k():
                    self.score += 5

                # 子因子C3： 1小时 RSI-6 低于35(短期超卖)且反弹
                if self.rsi_1h_factors.get_rebound(threshold=Decimal("35")):
                    self.score += 5

        return self.score >= 25  # 任一子因子满足


class ModelLTypeRebound(ModelBase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        self.name = "model_l_type_rebound"
        self.name_str = "日线EMA多头+4小时布林带形成L形状，1小时布林带下轨反弹结构"
        self.curr_price = self.kline_1h_factors.kline_list[0].close_price
        self.score = 0

    def get_recommend_price(self):
        return {
            "recommend_bid_price": self.kline_1h_factors.bb_list[0].bblower,
        }

    def is_detected(self):
        if self.has_bearish():
            return False

        # 前置条件：更大周期的日线的EMA多头排列+4小时布林带形成L形状
        if self.kline_1d_factors.is_ema_bullish_stack(window_size=5) \
                and self.kline_4h_factors.has_l_shape():
            self.score += 10

            # 条件D：当前k线的最低价跌破下轨，收盘价回到下轨上方
            is_1h_structure = self.kline_1h_factors.get_fake_breakdown_by_bb(index=0, is_low=True)
            if is_1h_structure:
                self.score += 10

                # 子因子D1：1小时的KDJ的J底部背离
                is_new_low_price = self.kline_1h_factors.is_new_low_price(3, index=1)
                if self.kdj_1h_factors.is_j_bullish_divergence(is_new_low_price, index=1, j_threshold=Decimal("10")):
                    self.score += 5

        # TODO:
        return self.score >= 20  # 任一子因子满足


class ModelWTypeRebound(ModelBase):
    """
    结构判断：
        定义时间窗 window_size=15（蜡烛图长度）：
            P1：找到过去15根内最低点（第一个低点）；
            P2：在 P1 后蜡烛内找到中间高点；
            P3：P2 后内再出现次低点，价格接近 P1，且不明显创新低
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        self.name = "model_w_type_rebound"
        self.name_str = "1小时布林带形成W形状，1小时布林带下轨反弹结构"
        self.curr_price = self.kline_1h_factors.kline_list[0].close_price
        self.score = 0

    def get_recommend_price(self):
        return {
            "recommend_bid_price": self.curr_price,
        }

    def is_detected(self):
        if self.has_bearish():
            return False

        if self._is_detected(self.kline_4h_factors.kline_list, self.macd_4h_factors.macd_list, 
                             self.kline_4h_factors.bb_list, self.rsi_4h_factors.rsi_list):
            return True
        elif self._is_detected(self.kline_1h_factors.kline_list, self.macd_1h_factors.macd_list, 
                               self.kline_1h_factors.bb_list, self.rsi_1h_factors.rsi_list):
            return True
        else:
            return False

    def _is_detected(self, kline_list, macd_list, bb_list, rsi_list):
        kline_factors = CandlestickFactor(kline_list, macd_list, bb_list)

        window_size = 15
        low_prices_list = [i.low_price for i in kline_list[:window_size]]
        p1_price = min(low_prices_list)
        p1_index = low_prices_list.index(p1_price)
        if p1_index == 0 or p1_index == 14:
            return False

        # 检查P1前的价格走势是否沿布林带下轨或快速下跌
        if not (
            # 检查是否沿布林带下轨运行
            kline_factors.is_along_lower_band(index=p1_index, n=window_size-p1_index) or
            # 检查是否快速下跌:开盘价高于上中轨均值且最低点低于中下轨均值
            (
                kline_list[window_size-1].open_price > (bb_list[window_size-1].bbupper + bb_list[window_size-1].bbmid)/Decimal("2") and
                p1_price < (bb_list[p1_index].bbmid + bb_list[p1_index].bblower)/Decimal("2")
            )
        ):
            return False

        high_prices_list = [i.high_price for i in kline_list[:p1_index]]
        if not high_prices_list:
            return False
        p2_price = max(high_prices_list)
        p2_index = high_prices_list.index(p2_price)
        # p2中间高点超过布林带中轨
        if not (bb_list[p2_index].bbmid < p2_index < (bb_list[p2_index].bbmid + bb_list[p2_index].bbupper)/Decimal("2")):
            return False

        low_prices_list = [i.low_price for i in kline_list[:p2_index]]
        if not low_prices_list:
            return False
        p3_price = min(low_prices_list)
        p3_index = low_prices_list.index(p3_price)

        if not (p3_price >= p1_price * Decimal("0.97")):
            return False

        if p3_index != 1:
            return False

        # 上面逻辑：价格结构满足 P1-P2-P3 的模式

        # 子因子W1：RSI 增强, RSI(P3) > RSI(P1)
        p3_near_rsi = min(rsi_list[p3_index-1].rsi, rsi_list[p3_index].rsi, rsi_list[p3_index+1].rsi)
        p1_near_rsi = min(rsi_list[p1_index-1].rsi, rsi_list[p1_index].rsi, rsi_list[p1_index+1].rsi)
        if p3_near_rsi > p1_near_rsi:
            self.score += 5

        # 子因子W2：成交量增加, vol(P3) > 1.5 * avg_vol
        # 子因子W3：MACD 金叉 / 柱体翻红	DIF>DEA 且 MACD>0

        return self.score >= 5


class ModelVTypeRebound(ModelBase):
    """
    1小时V型，从下轨到中轨，过中轨后的k线的收盘价没有下落中轨，平行布林带口袋向上贴上轨。

    结构判断：
        定义时间窗 window_size=18（蜡烛图长度）：
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        self.name = "model_v_type_rebound"
        self.name_str = "1小时k线形成V形状，1小时布林带开始沿上轨并稳定住"
        self.curr_price = self.kline_1h_factors.kline_list[0].close_price
        self.score = 0

    def get_recommend_price(self):
        return {
            "recommend_bid_price": self.curr_price,
        }

    def is_detected(self):
        window_size = 18
        low_prices_list = [i.low_price for i in self.kline_1h_factors.kline_list[:window_size]]
        min_low_price = min(low_prices_list)
        min_low_price_index = low_prices_list.index(min_low_price)

        if not self.kline_1h_factors.is_ema_golden_cross(index=0):
            return False

        count_kline_in_bbmid_range = [
            self.kline_1h_factors.kline_list[i].open_price < self.kline_1h_factors.bb_list[i].bbmid <
            self.kline_1h_factors.kline_list[i].close_price for i in range(min_low_price_index)]
        # 判断中间低点到右边界，是否连续上涨
        if sum(count_kline_in_bbmid_range) > 1:
            return False

        count_ema_death_cross = [self.kline_1h_factors.is_ema_death_cross(index=i)
                                 for i in range(min_low_price_index, window_size)]
        # 判断中间低点到左边界，是否ema死叉向下
        if sum(count_ema_death_cross) > 1:
            return False

        # 子因子V1：4小时KDJ金叉
        if self.kdj_4h_factors.get_curr_golden_cross():
            self.score += 5

        return self.score >= 5
