#! /usr/bin/env python
# -*- coding: UTF-8 -*-

"""
🧠
"""

import logging
from decimal import Decimal

from models.factor import CandlestickFactor, MacdFactor, KdjFactor, RsiFactor
from models.strategy import ModelTopRise, ModelOscillation, ModelBollMidRebound, ModelBollLowReboundBullishSideways, \
    ModelBollLowReboundBullishDown, ModelLTypeRebound, ModelWTypeRebound, ModelVTypeRebound
from utils.indicators import check_near_low

logger = logging.getLogger(__name__)


class StrategyHandle:
    def __init__(self, kline_list_4h, kline_list_1h, kline_list_15m,
                 bb_list_4h, bb_list_1h, bb_list_15m,
                 macd_list_1d, macd_list_4h, macd_list_1h, macd_list_15m,
                 kdj_list_1d, kdj_list_4h, kdj_list_1h, kdj_list_15m,
                 rsi_list_4h, rsi_list_1h, rsi_list_15m):
        self.symbol = kline_list_1h[0].symbol
        
        # 保存原始数据
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

    def _align_data(self, kline_list, bb_list, macd_list, kdj_list, rsi_list):
        """
        确保同一时间周期的数据基于 open_ts 对齐
        以 kline 数据为基准
        """
        if not kline_list:
            raise ValueError("kline_list is empty")

        kline_map = {k.open_ts: k for k in kline_list}
        bb_map = {b.open_ts: b for b in bb_list}
        macd_map = {m.opening_ts: m for m in macd_list}
        kdj_map = {k.open_ts: k for k in kdj_list}
        rsi_map = {r.open_ts: r for r in rsi_list}
        
        # 使用 kline 的时间戳作为基准
        all_ts = sorted(kline_map.keys(), reverse=True)
        
        # 重新排序数据
        aligned_kline = []
        aligned_bb = []
        aligned_macd = []
        aligned_kdj = []
        aligned_rsi = []
        
        for ts in all_ts:
            if ts not in bb_map or ts not in macd_map or ts not in kdj_map or ts not in rsi_map:
                continue
                
            aligned_kline.append(kline_map[ts])
            aligned_bb.append(bb_map[ts])
            aligned_macd.append(macd_map[ts])
            aligned_kdj.append(kdj_map[ts])
            aligned_rsi.append(rsi_map[ts])
            
        # 验证所有列表长度一致
        assert len(aligned_kline) == len(aligned_bb) == len(aligned_macd) == len(aligned_kdj) == len(aligned_rsi), \
            f"数据长度不一致: kline={len(aligned_kline)}, bb={len(aligned_bb)}, macd={len(aligned_macd)}, kdj={len(aligned_kdj)}, rsi={len(aligned_rsi)}"
            
        return aligned_kline, aligned_bb, aligned_macd, aligned_kdj, aligned_rsi

    def prepare_data(self):
        """
        准备数据：对齐数据并初始化因子
        """
        # 对齐数据
        self.kline_list_4h, self.bb_list_4h, self.macd_list_4h, self.kdj_list_4h, self.rsi_list_4h = \
            self._align_data(self.kline_list_4h, self.bb_list_4h, self.macd_list_4h, self.kdj_list_4h, self.rsi_list_4h)
            
        self.kline_list_1h, self.bb_list_1h, self.macd_list_1h, self.kdj_list_1h, self.rsi_list_1h = \
            self._align_data(self.kline_list_1h, self.bb_list_1h, self.macd_list_1h, self.kdj_list_1h, self.rsi_list_1h)
            
        # self.kline_list_15m, self.bb_list_15m, self.macd_list_15m, self.kdj_list_15m, self.rsi_list_15m = \
        #     self._align_data(self.kline_list_15m, self.bb_list_15m, self.macd_list_15m, self.kdj_list_15m, self.rsi_list_15m)

        # 初始化因子
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
        # 准备数据
        self.prepare_data()

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
        self.prepare_data()
        
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

    def get_symbol_score(self, symbol: str) -> dict:
        """
        计算symbol的进出场分数
        
        Args:
            symbol: 交易对符号
            
        Returns:
            包含进出场分数的字典
        """
        # 准备数据
        self.prepare_data()
        
        entry_score_info = self.get_buy_by_multi_factor_score_info(self.kline_list_1h[0].close_price)
        
        # 计算出场分数 (0-1)  
        exit_score_info = self.get_exit_by_multi_factor_score_info(self.kline_list_1h[0].close_price)
        
        # 根据分数给出推荐
        # recommendation = self._get_recommendation(entry_score, exit_score)
        
        return {
            "symbol": symbol,
            "entry_score": sum(entry_score_info.values()),
            "exit_score": "TODO",
            "exit_score_info": exit_score_info,
            "recommendation": "TODO",
        }
        
    def get_exit_by_multi_factor_score_info(self, current_price):
        sell_info_1 = self._get_sell_direction_active_taking_profit(current_price)
        sell_info_2 = self._get_sell_direction_stop_loss(current_price)
        sell_info_3 = self._get_exit_score()
        
        return {
            "sell_info_1": sell_info_1,
            "sell_info_2": sell_info_2,
            "sell_info_3": sell_info_3,
        }
        
    def _calculate_exit_score(self) -> float:
        # TODO
        """计算出场分数"""
        score = 0.0
        max_score = 100.0
        
        # 基于现有的_get_exit_score等逻辑计算出场分数
        try:
            # 使用现有的退出评分逻辑
            exit_score_detail = self._get_exit_score()
            if exit_score_detail:
                # 解析现有的分数逻辑
                if "macd_4h_downtrend" in exit_score_detail:
                    score += 10
                if "kdj_1h_j_80_downtrend" in exit_score_detail:
                    score += 10
                if "kdj_1d_over_bought" in exit_score_detail:
                    score += 15
                if "kdj_4h_over_bought" in exit_score_detail:
                    score += 15
                if "vol_1h_stagflation" in exit_score_detail:
                    score += 15
                    
        except Exception:
            pass
            
        return min(score / max_score, 1.0)
    
    def _get_recommendation(self, entry_score: float, exit_score: float) -> str:
        # TODO: 根据进出场分数给出推荐
        """根据进出场分数给出推荐"""
        if entry_score > 0.6 and exit_score < 0.3:
            return "buy"
        elif exit_score > 0.6 and entry_score < 0.3:
            return "sell"
        else:
            return "hold"

    def get_buy_by_multi_factor_score_info(self, current_price):
        """
        多因子打分策略:

        结构分-离散状态(定性)-固定分
        趋势分-连续变化(定量)-动态分

        趋势因子(35分)：
            *. 4 小时 EMA12 > EMA26（current_EMA12 > current_EMA26 多头排列） → +10 分 *（趋势核心）*
            *. 4 小时 EMA12+EMA26的趋势得分 -> 动态分数：
                *. (curr_ema12 < prev_ema12,短期动能减弱 -> -3 分)
                *.（curr_ema12 >= prev_ema12 → +3 分）
                *. (curr_ema26 < prev_ema26,中期动能减弱 -> -5 分)
                *. (ema12和ema26差距在缩小，动能衰减 -> -2 分)
                *. (ema12和ema26差距在扩大，趋势加速 -> +2 分)
            *. 1 小时 EMA12 > EMA26（current_EMA12 > current_EMA26 多头排列） → +5 分 *（短期趋势确认）*
            *. 1 小时 EMA12+EMA26的趋势得分 -> 动态分数：
                *. (curr_ema12 < prev_ema12,短期动能减弱 -> -1.5 分)
                *.（curr_ema12 >= prev_ema12 → +1.5 分）
                *. (curr_ema26 < prev_ema26,中期动能减弱 -> -2.5 分)
                *.（curr_ema26 > prev_ema26 → +2.5 分)
                *. (1小时的EMA12和EMA26的近7根线的距离趋势下降且扩大 -> -5 分)
            *. 1 小时 MACD 的相对趋势上升 → +5 分;
                *. (macd没有三连升 -> -3 分)
            *. 日线 MACD > 0 → +2 分
            *. 4 小时 MACD > 0 → +5 分;动态调整分数：
                *.（macd当前线三连降 -> -3 分）
        短期动能因子(35分)
            *. 4 小时 KDJ 动态得分：
                *. (4 小时 KDJ 3 连升 → +10 分;动态调整分数)：（J<= 20 -> -10 分）（20<J<=95 -> 不扣分）（95 < J ≤ 100 -> 按比例递减, 10 - (J-95) * 1）（ J > 100 -> -10 分）
                *. (4 小时 KDJ 刚好处于金叉 → +5 分。)
            *. 1 小时 KDJ 动态得分：
                *. (1 小时 KDJ 2 连升 → +5 分。)
                *. (1 小时 KDJ 没死叉 → +5 分；动态调整分数：
                    *.（KDJ 处于震荡状态 -> -2 分）（当前RSI>70 -> -2 分）)
                *. (1小时的KDJ的前两根线均大于100 -> -5 分)
                *. (1小时KDJ的J值从低位(<=15)上升至20以上 → +5 分。)
                *. (1小时KDJ在低位（J<20）形成金叉 → +5分)
            *. 4 小时 RSI 动态得分:
                *. (4 小时 RSI-6 突破 60，增强趋势信号 → +3 分。)
                *. (4 小时 RSI-6 在 45-65（中期健康区间） → +3 分。)
                *. (4 小时 RSI-6 连续 3 根 K 线递增 → +3 分。)
                *. (4 小时 RSI-6 上涨背离 -> -5分)
                *. (4 小时 RSI-6 下跌背离 -> +5分)
                *. 4小时 RSI < 30 且 近2根K线开始反弹（当前 RSI > 前一 RSI）→ +5 分
            *. 1 小时 RSI 动态得分：
                *. (1 小时 RSI-6 低于 40（短期超卖）且反弹 → +5 分。)
                *. (1小时 RSI-6 连续3根线递增 -> +5 分。)
                *. (1小时 RSI-6 突破 65 后回踩 60，视为回调进场点（多单）-> +3 分。)
                *. (1小时 RSI-6 从低位突破50 -> +5 分。)
                *. (1小时的当前线RSI大于80或者前线RSI大于80 -> -5 分)
                *. (1小时RSI-6从低于25上穿30 -> +5 分。)
            *. 4小时的布林带的得分：
                *.（最高价突破上轨但当前价低于上轨，可能是假突破 -> -3 分）
                *.（开盘价突破上轨，当前价突破上轨，高开高走 -> -3 分）
                *.（4小时的当前k线最高价突破上轨且为十字线 -> -5 分）
            *. 1小时的布林带的得分：
                *. 1小时的前K线(或者当前线)为长上影线且其最高价击穿上轨为假突破 -> -5 分
                *. 1小时的当前价格 > (上轨 + 中轨)/2 -> -5 分
                *. 1小时的当前k线，首次冲高 + 上轨附近 -> -20 分
                *. 1小时的K线沿着下轨运行 -> -10 分
                *. 1小时的前k线收盘价在布林带的下半带的1/2的区间内 -> +5 分;1小时的中轨大于当前价 -> +8分;中轨 <= 当前价格 < 中轨 + (上轨-中轨)*10% -> +5分
            *. 4小时的K线形态的得分：
                *.（当前4小时k线形成上影线 -> -2 分）
            *. 1小时的k线形态的得分：
                *.（1小时k线的前根线为长十字线 + 下影线更长 -> -3 分）

        成交量因子(20分)
            1. 4 小时成交量 > 5 根均值 且 > 10 根均值 → +10 分。
            2. 1 小时成交量 > 5 根均值 * 1.3 → +5 分；动态调整分数：（当前k线的最高价未突破前5根线的最高价 -> -3 分）
            3. 4 小时成交量 > 5 根均值 且 1 小时成交量 > 5 根均值 → +5 分。
        支持阻力因子(10分)
            1. 1小时最低价靠近支撑位(下轨或者中轨) -> +5 分。
            2. 1小时最低价处于阻力区间内 -> +5 分。
        整体市场情绪因子(5分)
            1. 当指数<20(极度恐惧)时 -> +5 分。
            2. 当指数>80(极度贪婪)时 -> -5 分。
        高位环境风险惩罚因子(-5分)
        触底反弹因子（20分）
        """
        score_info = {}

        # 趋势因子(35分)
        kline_4h_factors = CandlestickFactor(self.kline_list_4h, self.macd_list_4h, self.bb_list_4h)
        ema_4h_factor = kline_4h_factors.get_ema_factor(is_bid=True)
        if ema_4h_factor.get("has_ema_stack"):
            score_info["4h_has_ema_stack"] = 10 # 4 小时 EMA12 > EMA26（current_EMA12 > current_EMA26 多头排列） → +10 分 *（趋势核心）*

        score_info["4h_has_ema_uptrend"] = self._get_adjust_score_4h_has_ema_uptrend(
            0, kline_4h_factors) # 4小时 EMA12和EMA26的趋势动态得分 →

        kline_1h_factors = CandlestickFactor(self.kline_list_1h, self.macd_list_1h, self.bb_list_1h)
        if kline_1h_factors.has_ema_bullish_alignment():
            score_info["1h_has_ema_stack"] = 5 # 1 小时 EMA12 > EMA26（current_EMA12 > current_EMA2 多头排列） → +5 分 *（短期趋势确认）*

        # prev_ema_trend_1h_info = kline_1h_factors.get_prev_ema_trend_factor()
        # if prev_ema_trend_1h_info["trend"] in ["parabolic_move", "modest_increase"]:
        score_info["1h_has_ema_uptrend"] = self._get_adjust_score_1h_has_ema_uptrend(
            0, kline_1h_factors) # 1小时 EMA12和EMA26的趋势动态得分 →

        macd_1h_factors = MacdFactor(self.macd_list_1h)
        prev_macd_trend_1h_info = macd_1h_factors.get_prev_trend_factor()
        if prev_macd_trend_1h_info["trend"] in ["parabolic_move", "modest_increase"]:
            score_info["1h_macd_uptrend"] = self._get_adjust_score_1h_macd_trend(
                5) # 1 小时 MACD 上升 → +5 分

        if self.macd_list_1d and self.macd_list_1d[0].macd > 0:
            score_info["1d_macd>0"] = 2 # 日线 MACD > 0 → +2 分

        macd_4h_factors = MacdFactor(self.macd_list_4h)
        if self.macd_list_4h[0].macd > 0:
            score_info["4h_macd_uptrend"] = self._get_adjust_score_4h_macd_uptrend(
                5, macd_4h_factors) # 4 小时 MACD > 0 → +5 分

        # 短期动能因子(35分)
        kdj_4h_factors = KdjFactor(self.kdj_list_4h)
        score_info["kdj_4h"] = self._get_adjust_score_kdj_4h(0, kdj_4h_factors)

        kdj_1h_factors = KdjFactor(self.kdj_list_1h)
        score_info["kdj_1h"] = self._get_adjust_score_kdj_1h(0, kdj_1h_factors)

        rsi_4h_factors = RsiFactor(self.rsi_list_4h)
        score_info["rsi_4h"] = self._get_adjust_score_rsi_4h(0, rsi_4h_factors, kline_4h_factors)

        rsi_1h_factors = RsiFactor(self.rsi_list_1h)
        score_info["rsi_1h"] = self._get_adjust_score_rsi_1h(0, rsi_1h_factors)

        score_info["boll_4h"] = self._get_adjust_score_boll_4h(
            0, current_price, kline_4h_factors
        )

        score_info["boll_1h"] = self._get_adjust_score_boll_1h(
            0, current_price, kline_1h_factors
        )

        score_info["kline_4h"] = self._get_adjust_score_kline_4h(0, kline_4h_factors)
        score_info["kline_1h"] = self._get_adjust_score_kline_1h(0, kline_1h_factors)

        # 成交量因子(20分)
        vol_4h_5_factor = kline_4h_factors.get_vol_factor(5)
        vol_4h_10_factor = kline_4h_factors.get_vol_factor(10)
        if vol_4h_5_factor.get("has_spike_volume") and vol_4h_10_factor.get("has_spike_volume"):
            score_info["vol_4h_continue_up"] = 10 # 4 小时成交量 > 5 根均值 且 > 10 根均值 → +10 分

        vol_1h_factor = kline_1h_factors.get_vol_factor(5)
        if vol_1h_factor.get("has_enhance_spike_volume"):
            score_info["vol_1h_up_1.3x"] = \
                self._get_adjust_score_vol_1h_up_13x(5, current_price, vol_1h_factor) # 1 小时成交量 > 5 根均值 * 1.3 → +5 分

        if vol_4h_5_factor.get("has_spike_volume") and vol_1h_factor.get("has_spike_volume"):
            score_info["vol_4h_1h_up"] = 5 # 4 小时成交量 > 5 根均值 且 1 小时成交量 > 5 根均值 → +5 分

        # 支持阻力因子(10分)
        near_info = None
        if kline_1h_factors.is_ema12_continue_down(window_size=3):
            if self.bb_list_1h[0].bbmid <= current_price < self.bb_list_1h[0].bbupper:
                near_info = check_near_low(self.kline_list_1h[:21][::-1], self.bb_list_1h[0].bbmid, self.bb_list_1h[0].bbupper, logger)
            elif self.bb_list_1h[0].bblower <= current_price < self.bb_list_1h[0].bbmid:
                near_info = check_near_low(self.kline_list_1h[:21][::-1], self.bb_list_1h[0].bblower, self.bb_list_1h[0].bbmid, logger)

        if near_info and near_info["is_near"]:
            score_info["1h_low_price_near_bb_support"] = 5 # 1小时最低价靠近支撑位 -> +5 分
        if near_info and near_info["price_structure_valid"]:
            score_info["1h_low_price_bb_resistance_range"] = 5 # 1小时最低价处于阻力区间内 -> +5 分

        # 整体市场情绪因子(5分)
        if self.get_fng_signal(buy=True) is True:
            score_info["fng_lt_20"] = 5 # 当指数<20(极度恐惧)时 -> +5 分。
        elif self.get_fng_signal(buy=True) is False:
            score_info["fng_lt_20"] = -5 # 当指数>80(极度贪婪)时 -> -5 分。

        # 高位环境风险惩罚因子(保留标签，进行状态识别)
        # 触底反弹因子(20分)

        # TODO:暂停多因子的独立叠加的计分
        # return {}

        sum_score = sum(score_info.values())
        if sum_score >= 40:
            logger.info(f"plot_gpt get_buy_score_info finish, symbol:{self.symbol}, score:{sum_score}, score_info:{score_info}")

        # if sum_score >= 60:
        #     return score_info
        # return {}
        return score_info

    def _get_adjust_score_4h_has_ema_uptrend(self, score, kline_4h_factors):
        if self.macd_list_4h[0].ema_12 < self.macd_list_4h[1].ema_12:
            score -= 3 # curr_ema12 < prev_ema12,短期动能减弱 -> -3 分
        else:
            score += 3 # current_EMA12 > prev_EMA12 → +3 分

        if self.macd_list_4h[0].ema_26 < self.macd_list_4h[1].ema_26:
            score -= 5 # curr_ema26 < prev_ema26,中期动能减弱 -> -5 分

        diff_trend = kline_4h_factors.get_ema_trend(window_size=5)
        if diff_trend["trend"] == "downward_spiral":
            score -= 2 # ema12和ema26差距在缩小，动能衰减 -> -2 分
        elif diff_trend["trend"] == "parabolic_move":
            score += 2 # ema12和ema26差距在扩大，趋势加速 -> +2 分
        return score

    def _get_adjust_score_vol_1h_up_13x(self, score, curr_price, vol_1h_factor):

        if ("prev_high_price" in vol_1h_factor) \
                and (vol_1h_factor["prev_high_price"] >= vol_1h_factor["curr_high_price"]):
            score -= 3 # 当前k线的最高价未突破前5根线的最高价 -> -3 分
        return score

    def _get_adjust_score_1h_macd_trend(self, score):
        if not (self.macd_list_1h[0].macd > self.macd_list_1h[1].macd > self.macd_list_1h[2].macd):
            score -= 3 # macd没有三连升 -> -3 分
        return score

    def _get_adjust_score_4h_macd_uptrend(self, score, macd_factors):
        if macd_factors.is_continue_down():
            score -= 3 # macd当前线三连降 -> -3 分
        return score

    def _get_adjust_score_1h_has_ema_uptrend(self, score, kline_1h_factors):
        if self.macd_list_1h[0].ema_12 < self.macd_list_1h[1].ema_12:
            score -= 1.5 # curr_ema12 < prev_ema12,短期动能减弱 -> -1.5 分
        else:
            score += 1.5 # current_EMA12 > prev_EMA12 → +1.5 分

        if self.macd_list_1h[0].ema_26 < self.macd_list_1h[1].ema_26:
            score -= 2.5 # curr_ema26 < prev_ema26,中期动能减弱 -> -2.5 分
        elif self.macd_list_1h[0].ema_26 > self.macd_list_1h[1].ema_26:
            score += 2.5 # curr_ema26 > prev_ema26 → +2.5 分

        if kline_1h_factors.get_ema_trend()["trend"] == "downward_spiral":
            score -= 5 # 1小时的EMA12和EMA26的近7根线的距离趋势下降且扩大 -> -5 分

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

    def _get_adjust_score_kdj_4h(self, score, kdj_4h_factors):
        curr_score_info = {}
        if kdj_4h_factors.get_uptrend(3):
            curr_score_info["kdj_4h_up"] = self._get_adjust_score_kdj_4h_up(10) # 4 小时 KDJ 3 连升 → +10 分

        if kdj_4h_factors.get_curr_golden_cross():
            curr_score_info["kdj_4h_golden_cross"] = 5 # 4 小时 KDJ 刚好处于金叉 → +5 分

        return score + sum(curr_score_info.values())

    def _get_adjust_score_kdj_1h(self, score, kdj_1h_factors):
        curr_score_info = {}
        if kdj_1h_factors.get_uptrend(2):
            curr_score_info["kdj_1h_up_signal"] = 5  # 1 小时 KDJ 2 连升 → +5 分

        if self.kdj_list_1h[0].k_val >= self.kdj_list_1h[0].d_val:
            curr_score_info["kdj_1h_no_death_cross"] = \
                self._get_adjust_score_kdj_1h_no_death_cross(5, kdj_1h_factors) # 1 小时 KDJ 没死叉 → +5 分

        if self.kdj_list_1h[1].j_val > Decimal("100") and self.kdj_list_1h[2].j_val > Decimal("100"):
            curr_score_info["overheat_risk_kdj_1h_too_hot"] = -5 # 1小时的KDJ的前两根线均大于100 -> -5 分

        if self.kdj_list_1h[0].j_val > Decimal("20") \
                and self.kdj_list_1h[1].j_val <= Decimal("15"): # 1小时KDJ的J值从低位(<=15)上升至20以上 → +5 分。
            curr_score_info["back_kdj_1h_pullback_15to20"] = 5

        if kdj_1h_factors.get_curr_golden_cross_by_threshold(Decimal("20")): # 1小时KDJ在低位（J<20）形成金叉 → +5分
            curr_score_info["back_kdj_1h_golden_cross_20low"] = 5

        return score + sum(curr_score_info.values())

    def _get_adjust_score_rsi_4h(self, score, rsi_4h_factors, kline_4h_factors):
        curr_score_info = {}
        if rsi_4h_factors.get_breakout(threshold=Decimal("60")):
            curr_score_info["rsi_4h_breakout_60"] = 3 # 4 小时 RSI-6 突破 60，增强趋势信号 → +3 分。

        if rsi_4h_factors.get_healthy_bound():
            curr_score_info["rsi_4h_healthy_bound_45to65"] = 3 # 4 小时 RSI-6 在 45-65（中期健康区间） → +3 分。

        if rsi_4h_factors.get_uptrend():
            curr_score_info["rsi_4h_uptrend"] = 3 # 4 小时 RSI-6 连续 3 根 K 线递增 → +3 分。

        window = 4
        prices = kline_4h_factors.get_donchian_channel(window_size=window)
        if self.kline_list_4h[0].high_price > prices["max_price"] and not (
                self.rsi_list_4h[0].rsi > max([i.rsi for i in self.rsi_list_4h[1:window+1]])):
            curr_score_info["rsi_4h_bearish_divergence"] = -5 # 4 小时 RSI-6 上涨背离 -> -5分

        if self.kline_list_4h[0].low_price < prices["min_price"] and not (
                self.rsi_list_4h[0].rsi < min([i.rsi for i in self.rsi_list_4h[1:window+1]])):
            curr_score_info["rsi_4h_bullish_divergence"] = 5 # 4 小时 RSI-6 下跌背离 -> +5分

        if (self.rsi_list_4h[0].rsi < Decimal("30")) \
                and (self.rsi_list_4h[0].rsi > self.rsi_list_4h[1].rsi):
            curr_score_info["back_rsi_4h_lt20_uptrend"] = 5 # 4小时 RSI < 30 且 近2根K线开始反弹（当前 RSI > 前一 RSI）→ +5 分

        return score + sum(curr_score_info.values())

    def _get_adjust_score_rsi_1h(self, score, rsi_1h_factors):
        curr_score_info = {}
        if rsi_1h_factors.get_rebound():
            curr_score_info["rsi_1h_rebound_40"] = 5 # 1 小时 RSI-6 低于 40（短期超卖）且反弹 → +5 分。

        if rsi_1h_factors.get_uptrend():
            curr_score_info["rsi_1h_uptrend"] = 5 # 1小时 RSI-6 连续3根线递增 -> +5 分

        if rsi_1h_factors.get_pullback_entry():
            curr_score_info["rsi_1h_pullback_65to60"] = 3 # 1小时 RSI-6 突破 65 后回踩 60，视为回调进场点（多单）-> +3 分。

        if rsi_1h_factors.get_breakout_from_low():
            curr_score_info["rsi_1h_breakout_from_low"] = 5 # 1小时 RSI-6 从低位突破50 -> +5 分。

        if self.rsi_list_1h[0].rsi > Decimal("80") or self.rsi_list_1h[1].rsi > Decimal("80"):
            curr_score_info["overheat_risk_rsi_1h_too_high"] = -5 # 1小时的当前线RSI大于80或者前线RSI大于80 -> -5 分

        if (self.rsi_list_1h[0].rsi >= Decimal("30")) and (self.rsi_list_1h[1].rsi < Decimal("25")):
            curr_score_info["back_rsi_1h_low_up_25to30"] = 5 # 1小时RSI-6从低于25上穿30 -> +5 分。

        return score + sum(curr_score_info.values())

    def _get_adjust_score_boll_4h(self, score, curr_price, kline_4h_factors):
        curr_score_info = {}
        high_price = self.kline_list_4h[0].high_price
        open_price = self.kline_list_4h[0].open_price

        if (curr_price < self.bb_list_4h[0].bbupper) and (high_price > self.bb_list_4h[0].bbupper):
            score -= 3 # 最高价突破上轨但当前价低于上轨，可能是假突破 -> -3 分

        if (curr_price > self.bb_list_4h[0].bbupper) and (open_price > self.bb_list_4h[0].bbupper):
            score -= 3 # 开盘价突破上轨，当前价突破上轨，高开高走 -> -3 分

        if self.kline_list_4h[0].high_price > self.bb_list_4h[0].bbupper and kline_4h_factors.is_crosshairs():
            curr_score_info["overheat_4h_upper_crosshairs"] = -5 # 4小时的当前k线最高价突破上轨且为十字线 -> -5 分

        return score + sum(curr_score_info.values())

    def _get_adjust_score_boll_1h(self, score, curr_price, kline_1h_factors):
        curr_score_info = {}

        for index in (0, 1):
            if kline_1h_factors.is_long_upper_shadow(index) and kline_1h_factors.get_fake_breakout_by_bb(index):
                # TODO: 假突破需要结合当前k线->回测判断是否需要 close_p<bbupper
                curr_score_info["overheat_fake_breakout"] = -5 # 1小时的前K线(或者当前线)为长上影线且其最高价击穿上轨为假突破 -> -5 分
                break

        if curr_price > (self.bb_list_1h[0].bbupper + self.bb_list_1h[0].bbmid)/Decimal("2"):
            curr_score_info["overheat_1h_bb_price_too_high"] = -5 # 1小时的当前价格 > (上轨 + 中轨)/2 -> -5 分

        if kline_1h_factors.get_first_breakout_by_bb():
            curr_score_info["first_breakout_by_bb"] = -20 # 1小时的当前k线，首次冲高 + 上轨附近 -> -20 分

        if kline_1h_factors.is_along_lower_band(n=4):
            curr_score_info["back_is_along_lower_band"] = -10 # 1小时的K线沿着下轨运行 -> -10 分

        if self.bb_list_1h[1].bblower < self.kline_list_1h[1].close_price <= (
                self.bb_list_1h[1].bblower + self.bb_list_1h[1].bbmid) / Decimal("2"):
            curr_score_info["back_low_bb_1h_level"] = 5 # 1小时的前k线收盘价在布林带的下半带的1/2的区间内 -> +5 分
        elif curr_price < self.bb_list_1h[0].bbmid:
            curr_score_info["back_mid_bb_1h_level"] = 8 # 1小时的中轨大于当前价 -> +8分;中轨 <= 价格 < 中轨 + (上轨-中轨)*10% -> +5分
        elif self.bb_list_1h[0].bbmid <= curr_price < (
                self.bb_list_1h[0].bbmid +(self.bb_list_1h[0].bbupper-self.bb_list_1h[0].bbmid)*Decimal("0.1")):
            curr_score_info["back_mid_bb_1h_level"] = 5

        return score + sum(curr_score_info.values())

    def _get_adjust_score_kline_4h(self, score, kline_4h_factors):
        if kline_4h_factors.is_long_upper_shadow():
            score -= 2 # 当前4小时k线形成上影线 -> -2 分
        return score

    def _get_adjust_score_kline_1h(self, score, kline_1h_factors):
        if kline_1h_factors.get_corsshairs_and_long_lower_shadow(index=1):
            score -= 3 # 1小时k线的前根线为长十字线 + 下影线更长 -> -3 分
        return score

    def _get_adjust_score_kdj_1h_no_death_cross(self, score, kdj_1h_factors):
        """
        过去 5 根 K 线的 KDJ 形态 - 判断 - kdj_1h_no_death_cross 分值
        5 根 K 线中 2 次金叉 + 2 次死叉 - 震荡行情，趋势不明朗 - 0 分
        5 根 K 线中 1 次金叉 + 1 次死叉 - 轻微震荡，可能仍有趋势 - 2 分
        5 根 K 线中 只出现 1 次金叉，之后一直维持 - 趋势稳定 - 5 分

        rsi > 70 -> -3 分
        """
        # TODO: 根据描述优化
        if kdj_1h_factors.get_sideways():
            score -= 2 # KDJ 处于震荡状态 -> -2 分

        if self.rsi_list_1h[0].rsi > Decimal("70"):
            score -= 2 # RSI>70 -> -2 分

        return score

    def get_fng_signal(self, buy=False):
        """
        策略信号-恐惧指数：
            <= 20, 买入信号
            >= 80, 卖出信号
            其他不做参考
        :return:
        """
        from cache.order import FearAndGreedIndexCache
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
