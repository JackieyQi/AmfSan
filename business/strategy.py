#! /usr/bin/env python
# -*- coding: UTF-8 -*-

"""
🧠
"""

from decimal import Decimal

from models.factor import CandlestickFactor, MacdFactor, KdjFactor, RsiFactor
from models.strategy import ModelTopRise, ModelOscillation, ModelBollMidRebound, ModelBollLowReboundBullishSideways, \
    ModelBollLowReboundBullishDown, ModelLTypeRebound, ModelWTypeRebound, ModelVTypeRebound


class StrategyHandle:
    def __init__(self, kline_list_4h, kline_list_1h, kline_list_15m,
                 bb_list_4h, bb_list_1h, bb_list_15m,
                 macd_list_1d, macd_list_4h, macd_list_1h, macd_list_15m,
                 kdj_list_1d, kdj_list_4h, kdj_list_1h, kdj_list_15m,
                 rsi_list_4h, rsi_list_1h, rsi_list_15m):
        self.symbol = kline_list_1h[0].symbol
        self.kline_list_4h = kline_list_4h
        self.kline_list_1h = kline_list_1h
        self.kline_list_15m = kline_list_15m
        self.bb_list_4h = bb_list_4h
        self.bb_list_1h = bb_list_1h
        self.bb_list_15m = bb_list_15m

        self.macd_list_1d = macd_list_1d
        self.macd_list_4h = macd_list_4h
        self.macd_list_1h = macd_list_1h
        self.macd_list_15m = macd_list_15m

        self.kdj_list_1d = kdj_list_1d
        self.kdj_list_4h = kdj_list_4h
        self.kdj_list_1h = kdj_list_1h
        self.kdj_list_15m = kdj_list_15m

        self.rsi_list_4h = rsi_list_4h
        self.rsi_list_1h = rsi_list_1h
        self.rsi_list_15m = rsi_list_15m

        self.initialize_factors()

    def initialize_factors(self):
        self.kline_1d_factors = CandlestickFactor(None, self.macd_list_1d, None)
        self.kline_4h_factors = CandlestickFactor(self.kline_list_4h, self.macd_list_4h, self.bb_list_4h)
        self.kline_1h_factors = CandlestickFactor(self.kline_list_1h, self.macd_list_1h, self.bb_list_1h)
        self.kline_15m_factors = CandlestickFactor(self.kline_list_15m, self.macd_list_15m, self.bb_list_15m)
        self.macd_4h_factors = MacdFactor(self.macd_list_4h)
        self.macd_1h_factors = MacdFactor(self.macd_list_1h)
        self.macd_15m_factors = MacdFactor(self.macd_list_15m)
        self.kdj_4h_factors = KdjFactor(self.kdj_list_4h)
        self.kdj_1h_factors = KdjFactor(self.kdj_list_1h)
        self.kdj_15m_factors = KdjFactor(self.kdj_list_15m)
        self.rsi_4h_factors = RsiFactor(self.rsi_list_4h)
        self.rsi_1h_factors = RsiFactor(self.rsi_list_1h)
        self.rsi_15m_factors = RsiFactor(self.rsi_list_15m)
        
    def check_in_by_model(self, last_model_msg, last_model_msg_2):
        kwargs = {
            "kline_1d_factors": self.kline_1d_factors,
            "kline_4h_factors": self.kline_4h_factors,
            "kline_1h_factors": self.kline_1h_factors,
            "kline_15m_factors": self.kline_15m_factors,
            "macd_4h_factors": self.macd_4h_factors,
            "macd_1h_factors": self.macd_1h_factors,
            "macd_15m_factors": self.macd_15m_factors,
            "kdj_4h_factors": self.kdj_4h_factors,
            "kdj_1h_factors": self.kdj_1h_factors,
            "kdj_15m_factors": self.kdj_15m_factors,
            "rsi_4h_factors": self.rsi_4h_factors,
            "rsi_1h_factors": self.rsi_1h_factors,
            "rsi_15m_factors": self.rsi_15m_factors,
        }
        model_top_rise = ModelTopRise(**kwargs)
        model_oscillation = ModelOscillation(**kwargs)

        if not last_model_msg and not last_model_msg_2:
            # 初始流程: 都判断
            if model_top_rise.is_in():
                model_top_rise.cal_recommend_price()
                return {"model_name": model_top_rise.name,
                        "recommend_bid_price": model_top_rise.recommend_bid_price,
                        "is_buy": True}
            if model_oscillation.is_in():
                return {"model_name": model_oscillation.name, }

        elif last_model_msg and not last_model_msg_2:
            if model_top_rise.name in last_model_msg:
                if model_oscillation.is_in():
                    return {"model_name": model_oscillation.name,}
            elif model_oscillation.name in last_model_msg:
                if "down" in last_model_msg:
                    if model_top_rise.is_in():
                        model_top_rise.cal_recommend_price()
                        return {"model_name": model_top_rise.name,
                                "recommend_bid_price": model_top_rise.recommend_bid_price,
                                "is_buy": True}
                elif "up" in last_model_msg:
                    if model_top_rise.is_in():
                        model_top_rise.cal_recommend_price()
                        return {"model_name": model_top_rise.name,
                                "recommend_bid_price": model_top_rise.recommend_bid_price,
                                "is_buy": True}

        elif last_model_msg and last_model_msg_2:
            if model_top_rise.name in last_model_msg_2 and model_oscillation.name in last_model_msg and "up" in last_model_msg:
                if model_top_rise.is_in_twice():
                    model_top_rise.cal_recommend_price()
                    return {"model_name": model_top_rise.name,
                            "recommend_bid_price": model_top_rise.recommend_bid_price,
                            "is_buy": True}
            elif model_top_rise.name in last_model_msg:
                if model_oscillation.is_in():
                    return {"model_name": model_oscillation.name,}
            elif model_oscillation.name in last_model_msg:
                if model_top_rise.is_in():
                    model_top_rise.cal_recommend_price()
                    return {"model_name": model_top_rise.name,
                            "recommend_bid_price": model_top_rise.recommend_bid_price,
                            "is_buy": True}
                if model_oscillation.is_in():
                    return {"model_name": model_oscillation.name, }

        return None

    def check_in_by_model_1h(self, last_model_msg):
        kwargs = {
            "kline_1d_factors": self.kline_1d_factors,
            "kline_4h_factors": self.kline_4h_factors,
            "kline_1h_factors": self.kline_1h_factors,
            "kline_15m_factors": self.kline_15m_factors,
            "macd_4h_factors": self.macd_4h_factors,
            "macd_1h_factors": self.macd_1h_factors,
            "macd_15m_factors": self.macd_15m_factors,
            "kdj_4h_factors": self.kdj_4h_factors,
            "kdj_1h_factors": self.kdj_1h_factors,
            "kdj_15m_factors": self.kdj_15m_factors,
            "rsi_4h_factors": self.rsi_4h_factors,
            "rsi_1h_factors": self.rsi_1h_factors,
            "rsi_15m_factors": self.rsi_15m_factors,
        }
                
        model_boll_mid_rebound = ModelBollMidRebound(**kwargs)
        if model_boll_mid_rebound.is_detected():
            model_recommend_price_data = model_boll_mid_rebound.get_recommend_price()
            return {"model_name": model_boll_mid_rebound.name,
                    "recommend_bid_price": model_recommend_price_data["recommend_bid_price"]}

        model_b = ModelBollLowReboundBullishSideways(**kwargs)
        if model_b.is_detected():
            model_recommend_price_data = model_b.get_recommend_price()
            return {"model_name": model_b.name,
                    "recommend_bid_price": model_recommend_price_data["recommend_bid_price"]}

        model_c = ModelBollLowReboundBullishDown(**kwargs)
        if model_c.is_detected():
            model_recommend_price_data = model_c.get_recommend_price()
            return {"model_name": model_c.name,
                    "recommend_bid_price": model_recommend_price_data["recommend_bid_price"]}

        model_d = ModelLTypeRebound(**kwargs)
        if model_d.is_detected():
            model_recommend_price_data = model_d.get_recommend_price()
            return {"model_name": model_d.name,
                    "recommend_bid_price": model_recommend_price_data["recommend_bid_price"]}

        model_w = ModelWTypeRebound(**kwargs)
        if model_w.is_detected():
            model_recommend_price_data = model_w.get_recommend_price()
            return {"model_name": model_w.name,
                    "recommend_bid_price": model_recommend_price_data["recommend_bid_price"]}

        model_v = ModelVTypeRebound(**kwargs)
        if model_v.is_detected():
            model_recommend_price_data = model_v.get_recommend_price()
            return {"model_name": model_v.name,
                    "recommend_bid_price": model_recommend_price_data["recommend_bid_price"]}

        return None
    
    def check_out_by_model(self, curr_model_msg):
        kwargs = {
            "kline_1d_factors": self.kline_1d_factors,
            "kline_4h_factors": self.kline_4h_factors,
            "kline_1h_factors": self.kline_1h_factors,
            "kline_15m_factors": self.kline_15m_factors,
            "macd_4h_factors": self.macd_4h_factors,
            "macd_1h_factors": self.macd_1h_factors,
            "macd_15m_factors": self.macd_15m_factors,
            "kdj_4h_factors": self.kdj_4h_factors,
            "kdj_1h_factors": self.kdj_1h_factors,
            "kdj_15m_factors": self.kdj_15m_factors,
            "rsi_4h_factors": self.rsi_4h_factors,
            "rsi_1h_factors": self.rsi_1h_factors,
            "rsi_15m_factors": self.rsi_15m_factors,
        }
        
        model_top_rise = ModelTopRise(**kwargs)
        model_oscillation = ModelOscillation(**kwargs)
        
        if model_top_rise.name in curr_model_msg:
            if model_top_rise.is_out():
                model_top_rise.cal_recommend_price()
                return {"model_name": model_top_rise.name,
                        "recommend_ask_price": model_top_rise.recommend_ask_price,
                        "is_sell": True}
                
        if model_oscillation.name in curr_model_msg:
            if model_oscillation.is_out():
                return {"model_name": model_oscillation.name,}
            
        return None
    
    def get_sell_direction(self, curr_price):
        if part_direction_info := self._get_sell_direction_active_taking_profit(curr_price):
            ask_plot_type = 6
            func_str = "_get_sell_direction_active_taking_profit"

            part_direction = part_direction_info.get("direction")
            recommend_ask_price = part_direction_info.get("recommend_ask_price")
        elif part_direction := self._get_sell_direction_stop_loss(curr_price):
            ask_plot_type = 7
            func_str = "_get_sell_direction_stop_loss"
        elif part_direction := self._get_exit_score():
            ask_plot_type = 8
            func_str = "_get_exit_score"
        else:
            return
        return part_direction

    def _get_sell_direction_active_taking_profit(self, curr_price):
        """
        主动止盈:
            * 若 KDJ J 值 > 90 且 MACD DIF 下降，视为强势过热信号，部分止盈。
            * 1小时: 当前价格接近或突破布林带上轨 + RSI > 80 + 成交量放大 + 价格未破新高 -> 止盈离场。

            * 1小时: 当前价格接近或突破布林带上轨 + RSI < 75 + MACD 柱状图收缩（即动能减弱）+ 附近价格未破新高
                * 4小时: 当前价格未沿着上轨运行 
                → 执行止盈
            
                    TODO: 2. 如果 RSI > 75 且 KDJ 仍金叉、MACD 扩张 → 等待下一根 K 线确认
                    TODO: 3. 如果连续3根K线都在上轨附近但价格未放量上涨 → 止盈

            TODO:* 前k的最高价突破中轨 + 当前k为十字线时，触发卖出。
        :return:
        """
        direction = ""

        if self.kdj_list_1h[0].j_val > 90 and self.macd_1h_factors.get_dif_downtrend():
            direction += "强势过热信号，部分止盈。"
            return {"direction": direction}

        if (self.kline_1h_factors.is_near_upper() 
                and self.rsi_list_1h[0].rsi > Decimal("80") 
                and self.kline_1h_factors.get_vol_factor(5).get("has_enhance_spike_volume", False) 
                and self.kline_list_1h[0].high_price < self.kline_1h_factors.get_donchian_channel(window_size=25)["max_price"]):
            direction += "止盈离场：1小时的RSI > 80 + 当前价格接近或突破布林带上轨 + 成交量放大 + 价格未破新高"
            return {"direction": direction}
        
        if (self.kline_1h_factors.is_near_upper(index=0, tolerance=Decimal("0.2")) 
                and self.rsi_list_1h[0].rsi < Decimal("75") 
                and self.macd_list_1h[0].macd < self.macd_list_1h[1].macd
                and not any([self.kline_list_1h[i].high_price < self.kline_1h_factors.get_donchian_channel(window_size=25)["max_price"] for i in range(2)])):
            if not self.kline_4h_factors.is_along_upper_band():
                direction += "价格逼近 1小时布林带上轨，RSI < 75 且 MACD 柱状图收缩（即动能减弱），优先止盈。"
                return {"direction": direction, "recommend_ask_price": curr_price}

        if self.is_bb_lower2mid_taking_profit():
            direction += "价格 1小时布林带下轨抵达中轨，(macd<0)/(kdj.j>80)/(RSI<75)，优先止盈。"
            return {"direction": direction}

        if self.kline_1h_factors.has_double_top():
            direction += "当前处于1小时双顶形态，止盈离场。"
            return {"direction": direction}

        kline_4h_factors = CandlestickFactor(self.kline_list_4h, self.macd_list_4h, self.bb_list_4h)
        if kline_4h_factors.is_bearish_engulfing_k(index=1):
            direction += "4小时的前k线看跌吞没，止盈离场。"
            return {"direction": direction}

        return {"direction": direction} if direction else {}

    def is_bb_lower2mid_taking_profit(self):
        """
        价格从下轨到达中轨，优先止盈
        """

        if self.kline_list_1h[2].high_price < self.bb_list_1h[2].bbmid \
                and not self.kline_1h_factors.is_near_mid(index=2, tolerance=Decimal("0.2")):
            if self.kline_1h_factors.is_near_mid(index=1, tolerance=Decimal("0.2")):
                if self.macd_list_1h[0].macd < 0 or self.kdj_list_1h[0].j_val > 80 or (self.rsi_list_1h[0].rsi < Decimal("75")):
                    return True
            return False

    def _get_sell_direction_stop_loss(self, curr_price):
        """
        止损：
        :param curr_price:
        :return:
        """
        direction = ""

        kline_1h_factors = CandlestickFactor(self.kline_list_1h, self.macd_list_1h, self.bb_list_1h)
        ema_1h_factor = kline_1h_factors.get_ema_factor(is_ask=True)
        if ema_1h_factor.get("has_death_cross"):
            direction += "1 小时 EMA12 和 EMA26 死叉，止损离场。"
            return direction

        return direction

    def _get_exit_score(self):
        """
        📊 领先信号（更早）：4H MACD 柱状图缩短：连续 2 根柱状图变短。-> +10 分
        📊 领先信号（更早）：1H KDJ J 线高位拐头：J 线 > 80 且开始向下。-> +10 分
        📊 动量因子：日线 KDJ 超买： K、D > 80 且 J 线向下。-> +15 分
        📊 动量因子：4H KDJ 超买： K、D > 80 且 J 线向下。-> +10 分
        🔻 价格行为因子：放量滞涨：1小时成交量暴增，但价格未创新高。-> +15 分

        """
        score_info = {}

        if self.macd_4h_factors.is_continue_down():
            score_info["macd_4h_downtrend"] = 10

        if (self.kdj_list_1h[1].j_val > 80) and (self.kdj_list_1h[1].j_val < self.kdj_list_1h[2].j_val):
            score_info["kdj_1h_j_80_downtrend"] = 10

        if self.kdj_list_1d and (self.kdj_list_1d[0].k_val > 80) and (self.kdj_list_1d[0].d_val > 80) \
                and (self.kdj_list_1d[0].j_val < self.kdj_list_1d[1].j_val):
            score_info["kdj_1d_over_bought"] = 15

        if (self.kdj_list_4h[0].k_val > 80) and (self.kdj_list_4h[0].d_val > 80) \
                and (self.kdj_list_4h[0].j_val < self.kdj_list_4h[1].j_val):
            score_info["kdj_4h_over_bought"] = 15

        window = 3
        max_price = self.kline_1h_factors.get_donchian_channel(window_size=window)["max_price"]
        vol_1h_factor = self.kline_1h_factors.get_vol_factor(window, rate_threshold=Decimal("2"))
        if vol_1h_factor.get("has_enhance_spike_volume") and self.kline_list_1h[0].high_price < max_price:
            score_info["vol_1h_stagflation"] = 15

        sum_score = sum(score_info.values())
        if sum_score >= 20:
            score_detail_text = ""
            for k, v in score_info.items():
                score_detail_text += f"{k}:{v}分;"
            return score_detail_text
        return ""
