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
from decimal import Decimal

from cache.order import MarketPriceLimitCache, FearAndGreedIndexCache
from models.market import KlineTable
from models.order import MacdTable, KdjTable
from models.user import EmailMsgHistoryTable
from settings.constants import PLOT_INTERVAL_CONFIG, INNER_GET_DELETE_LIMIT_PRICE_URL, INNER_GET_SUBMIT_LIMIT_PRICE_URL
from utils.common import ts2bjfmt
from utils.indicators import analyze_list_trend, calculate_bollinger_bands, calculate_cv, analyze_crossovers, \
    enhanced_analyze_by_groups
from utils.templates import template_gpt_plot_trend_following_strategy_notice, \
    template_gpt_plot_short_term_strategy_notice, template_gpt_plot_bull_run_strategy_notice
from .base import BasePlotHandle

logger = logging.getLogger(__name__)


class PlotGptHandle(BasePlotHandle):
    def __init__(self, symbol):
        super().__init__()
        self.symbol = symbol
        self.email_title = f"{symbol} GPT Plot Notice"

        self._kline_list_4h = None
        self._kline_list_1h = None
        self._macd_list_1d = None
        self._macd_list_4h = None
        self._macd_list_1h = None
        self._kdj_list_1d = None
        self._kdj_list_4h = None
        self._kdj_list_1h = None

        if "1h" not in PLOT_INTERVAL_CONFIG:
            raise Exception("Interval 1h miss.")
        if "4h" not in PLOT_INTERVAL_CONFIG:
            raise Exception("Interval 4h miss.")
        if "1d" not in PLOT_INTERVAL_CONFIG:
            raise Exception("Interval 1d miss.")

    @property
    def kline_list_4h(self):
        if self._kline_list_4h is None:
            self._kline_list_4h = self.get_kline_list("4h", limit_count=4)
        return self._kline_list_4h

    @property
    def kline_list_1h(self):
        if self._kline_list_1h is None:
            self._kline_list_1h = self.get_kline_list("1h", limit_count=11)
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
            self._kdj_list_4h = self.get_kdj_list("4h", limit_count=3)
        return self._kdj_list_4h

    @property
    def kdj_list_1h(self):
        if self._kdj_list_1h is None:
            self._kdj_list_1h = self.get_kdj_list("1h", limit_count=8)
        return self._kdj_list_1h

    def has_limit_price_check(self):
        all_limit_price = MarketPriceLimitCache.hgetall()
        if not all_limit_price:
            return False

        if "btcusdt" in all_limit_price:
            del all_limit_price["btcusdt"]

        if not all_limit_price:
            return False
        return True

    def get_support_resistance_level(self, interval):
        """
        支撑位: 布林带下轨
        阻力位: 布林带上轨
        """
        if interval == "1d":
            macd_list = self.macd_list_1d[:27]
        elif interval == "4h":
            macd_list = self.macd_list_4h[:27]
        elif interval == "1h":
            macd_list = self.macd_list_1h[:27]
        else:
            raise ValueError(f"get_support_resistance_level, interval:{interval}")

        close_prices_list, ema_list = [], []
        for i, row in enumerate(macd_list):
            if i == 0:
                # current_close_price = row.closing_price
                continue
            close_prices_list.append(row.closing_price)
            ema_list.append(row.ema_26)

        last_higher_band, last_lower_band = calculate_bollinger_bands(close_prices_list[::-1], ema_list[::-1])
        return last_higher_band, last_lower_band

    def trend_following_strategy_reformat_notice(self, direction, current_data):
        return template_gpt_plot_trend_following_strategy_notice(self.symbol, direction, current_data.open_ts)

    def short_term_strategy_reformat_notice(self, direction, current_kdj_1h, current_price, send_ts, close_monitor_url, set_limit_price_url):
        return template_gpt_plot_short_term_strategy_notice(
            self.symbol, direction, current_kdj_1h.open_ts, current_price, send_ts, close_monitor_url, set_limit_price_url)

    def bull_run_strategy_reformat_notice(self, open_ts, current_price, send_ts, close_monitor_url, set_limit_price_url):
        return template_gpt_plot_bull_run_strategy_notice(
            self.symbol, open_ts, current_price, send_ts, close_monitor_url, set_limit_price_url)

    def get_kline_list(self, interval, limit_count=18):
        query = (
            KlineTable.select().where(
                KlineTable.symbol == self.symbol,
                KlineTable.interval_val == interval,
            ).order_by(KlineTable.id.desc()).limit(limit_count)
        )
        query_list = [i for i in query]
        if not query_list:
            return
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
        query_list = [i for i in query]
        if not query_list:
            return
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
        query_list = [i for i in query]
        if not query_list:
            return
        if len(query_list) < limit_count:
            return
        return query_list

    async def check(self, limit_count=7):
        for interval in ["1d", "4h", "1h"]:
            if interval == "1h":
                continue
            elif interval == "4h":
                macd_list = self.macd_list_4h
            elif interval == "1d":
                macd_list = self.macd_list_1d
            else:
                continue

            now_macd_data, last_macd_data = macd_list[0], macd_list[1]

            now_ts = int(time.time())
            interval_sec = PLOT_INTERVAL_CONFIG[interval]["interval_sec"]
            if now_macd_data.opening_ts < (now_ts - interval_sec * limit_count):
                self.result[
                    self.symbol
                ] = f"""
                        <br><a>Error: no lastest macd data, {self.symbol}:{interval}</a>
                        <br><a>opening_ts:{ts2bjfmt(now_macd_data.opening_ts)}</a>
                        <br><a>now_ts:{ts2bjfmt(now_ts)}</a>
                        """

                return await self.send_msg(self.email_title, "".join(self.result.values()))

        await self.short_term_strategy(limit_count)
        await self.bull_run_strategy()

    def get_signal_count_status(self, *args):
        true_count = sum([*args])
        false_count = len([*args]) - true_count

        if true_count > false_count:
            return "增强"
        elif true_count < false_count:
            return "减弱"
        else:
            return "持衡"

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
                return
        else:
            if fng_index <= 20:
                return False
            elif fng_index >= 80:
                return True
            else:
                return

    async def short_term_strategy(self, limit_count):
        """
        短线快进快出策略
            主要工具：1小时KDJ+4小时MACD/日线MACD
            触发条件：核心信号满足+任意一个辅助信号满足即可触发买入，这样可以避免因为条件过多而错失信号。
        📈 买入信号
            1. 4小时MACD：DIF上穿DEA；或者 日线MACD：DIF上穿DEA。确认趋势反转后，再考虑买入。
            2. 日线KDJ刚形成死叉，说明趋势向下，不要向下考虑买入。
            3. 1小时KDJ的值均大于35，表示超卖反弹，增强买入信号，接着考虑第4点。
            4. 1小时MACD：最近7根线MACD柱状图的下行趋势减弱，表示下跌趋势减缓，接着考虑买入的辅助信号。
            5. 1小时级别击穿前低价：当前1小时的最低价，小于前10根1小时线的最低价，下跌趋势延续，不要向下考虑。
                5.1. (或)当前价格 **大于 4小时布林带下轨值**，未击穿支撑位，增强买入信号。
                5.2. (或)1小时KDJ **最近3条线，有接近死叉或金叉**，增强买入信号。
                5.3. (或)4小时K线的 **近三条的最高价逐步下降**，表示下跌压力依旧很大，1小时KDJ均值小于20附近，增强买入信号。
                5.4. (或)1小时成交量 **高于过去10根均值**，资金流入，增强买入信号。
                5.5. (或)4小时成交量 **高于过去3根均值**，资金持续流入，增强买入信号。
        📉 卖出信号
            1. 4小时MACD上行：DIF上穿DEA；或者 日线MACD上行：DIF上穿DEA（多头排列或者底背离）。
            2. 1小时KDJ的J值小于80时，判断是否趋势向下。
                2.1. 1小时的最新3条线的J值均小于50，表示市场没有上涨动能，考虑挂买入价卖出。
                2.2. 1小时的最新2根线的J值向上，表示可能存在反弹，不考虑挂单卖出。
                2.3. 1小时的K线的最新2根线，价格区间没有上涨，表示下跌信号增强，考虑挂单卖出。

            3. 1小时KDJ的J值在80附近，表示超买出现，开始考虑出场。
                3.1. 1小时MACD的当前时间段的值处于金叉，表示持续上涨，考虑持仓观望。
                3.2. 4小时MACD的当前时间段的值处于金叉，表示持续上涨，考虑持仓观望。
                    3.2.1. (或)1小时MACD：最近7根线MACD柱状图的上行趋势减弱，表示上涨趋势减缓，表示出场信号加强。
                    3.2.2. (或)当前1小时最高价，小于前面3根1小时线的最高价，表示价格受阻，超买回调趋势加强，表示出场信号加强。
                    3.2.3. (或)当前价格，在1小时布林带上轨且回落0.5%，表示出场信号加强。
                    3.2.4. (或)4小时MACD的最近2根柱状图，向下扩大，表示出场信号加强。
                    3.2.5. (或)4小时KDJ的最近2个时间段，K线和J线均下跌，表示出场信号加强。

        ⚠️ 注意：快进快出策略适合高频短线交易者，如果在趋势不明朗的震荡行情中，信号可能会频繁“假死叉”和“假金叉”。
        """
        if self.macd_list_1d[0].macd < 0 and self.macd_list_4h[0].macd < 0:
            return

        current_price = None
        all_signals_dict = {}

        close_monitor_url = f"{INNER_GET_DELETE_LIMIT_PRICE_URL}{self.symbol}"
        set_limit_price_url = ""

        # TODO: 全仓改分仓
        if not self.has_limit_price_check():
            if (self.kdj_list_1d[0].j_val < self.kdj_list_1d[0].d_val) \
                    and (self.kdj_list_1d[1].j_val > self.kdj_list_1d[1].d_val):
                return

            current_kdj_1h = self.kdj_list_1h[0]
            if current_kdj_1h.k_val > Decimal("35") \
                    or current_kdj_1h.d_val > Decimal("35") or current_kdj_1h.j_val > Decimal("35"):
                return

            # TODO: 手动回测-是否改为相对趋势
            current_trend_macd_1h, _ = analyze_list_trend([i.macd for i in self.macd_list_1h[:7]][::-1])
            if current_trend_macd_1h in ["downward_spiral", ]:
                return

            current_1h_low_price = self.kline_list_1h[0].low_price
            last_1h_low_price = min([i.low_price for i in self.kdj_list_1h[1:11]])
            if current_1h_low_price < last_1h_low_price:
                return

            current_price = self.macd_list_1h[0].closing_price

            resistance_level, support_level = self.get_support_resistance_level("4h")
            check_price_fall_signal = current_price > support_level
            all_signals_dict["check_price_fall_signal"] = check_price_fall_signal

            check_cv_cross_signal = False
            # TODO: 窗口大小，KDJ三线是否凑集
            for _kdj in self.kdj_list_1h[:8]:
                _cv = calculate_cv([_kdj.k_val, _kdj.d_val, _kdj.j_val])
                if _cv == 0:
                    check_cv_cross_signal = True
                    break
            all_signals_dict["check_cv_cross_signal"] = check_cv_cross_signal

            check_kdj_20_signal = False
            high_prices_4h_list = [i.high_price for i in self.kline_list_4h[:3]]
            if all(x < y for x, y in zip(high_prices_4h_list, high_prices_4h_list[1:])) is True:
                if current_kdj_1h.k_val < Decimal("20") and current_kdj_1h.d_val < Decimal("20") \
                        and current_kdj_1h.j_val < Decimal("20"):
                    check_kdj_20_signal = True
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
            all_signals_dict["check_4h_volume_up_signal"] = check_4h_volume_up_signal

            if current_1h_volume > last_mean_1h_volume:
                check_1h_volume_up_signal = True
            else:
                check_1h_volume_up_signal = False
            all_signals_dict["check_1h_volume_up_signal"] = check_1h_volume_up_signal

            check_fng_signal = self.get_fng_signal(buy=True)
            if check_fng_signal is not None:
                all_signals_dict["check_fng_signal"] = check_fng_signal

            if any(list(all_signals_dict.values())) is not True:
                return

            signal_status = self.get_signal_count_status(*all_signals_dict.values())

            direction = f" 🟢 短线高频交易(策略待优化): 📈 买入信号, " \
                        f"<br>总体信号-<b>{signal_status}</b>" \
                        f"<br>建议支撑位:{support_level}, 建议阻力位:{resistance_level}， " \
                        f"<br>辅助信号：价格未击穿支撑位: {check_price_fall_signal}, " \
                        f"<br>辅助信号：1小时KDJ有交叉: {check_cv_cross_signal}, " \
                        f"<br>辅助信号：1小时KDJ超卖: {check_kdj_20_signal}, " \
                        f"<br>辅助信号：1小时交易量流入增加：{check_1h_volume_up_signal}, " \
                        f"<br>辅助信号：4小时交易量流入增加：{check_4h_volume_up_signal}," \
                        f"<br>总信号：{all_signals_dict}"

            set_limit_price_url = f"{INNER_GET_SUBMIT_LIMIT_PRICE_URL}?" \
                                  f"symbol={self.symbol}&low_price={support_level}&high_price={resistance_level}"

        elif MarketPriceLimitCache.hget(self.symbol):
            limit_price = MarketPriceLimitCache.hget(self.symbol)
            if not limit_price:
                set_time, limit_low_price, limit_high_price = 0, "", ""
            else:
                set_time, limit_low_price, limit_high_price = limit_price.split(":")
            set_time = int(set_time)
            if not set_time:
                hours_diff = None
            else:
                hours_diff = (int(time.time()) - set_time) // 3600

            current_kdj_1h = self.kdj_list_1h[0]
            latest_kdj_1h_list = self.kdj_list_1h[:3]
            if current_kdj_1h.j_val <= Decimal("80"):
                for _kdj in latest_kdj_1h_list:
                    if _kdj.j_val >= Decimal("50"):
                        return

                if current_kdj_1h.j_val > latest_kdj_1h_list[1].j_val:
                    return

                for i in range(len(self.kline_list_1h[:2]) - 1):
                    if self.kline_list_1h[i].open_price > self.kdj_list_1h[i+1].open_price:
                        return
                    if self.kline_list_1h[i].close_price > self.kline_list_1h[i+1].close_price:
                        return

                direction = f" 🔴⚠️🔴短线高频交易(策略待优化): 📉 卖出信号, \n\n\b<br>上涨受阻，挂卖单在买入价->⌛️等待卖出！" \
                            f"<br>持仓时间：{hours_diff}"

            else:
                if self.macd_list_1h[1].macd < 0 and self.macd_list_1h[0].macd >= 0:
                    return
                if self.macd_list_4h[1].macd < 0 and self.macd_list_4h[0].macd >= 0:
                    return

                current_trend_macd_1h, _ = enhanced_analyze_by_groups([i.macd for i in self.macd_list_1h[:18]][::-1])
                check_trend_stalled_signal = current_trend_macd_1h not in ["parabolic_move", ]
                all_signals_dict["check_trend_stalled_signal"] = check_trend_stalled_signal

                high_prices_list = [i.high_price for i in self.kline_list_1h[:4]]
                check_price_resistance_signal = high_prices_list[0] < max(high_prices_list[1:])
                all_signals_dict["check_price_resistance_signal"] = check_price_resistance_signal

                current_price = self.macd_list_1h[0].closing_price
                resistance_level_1h, support_level_1h = self.get_support_resistance_level("1h")
                if current_price > resistance_level_1h \
                        and (high_prices_list[0] - current_price)/high_prices_list[0] >= Decimal("0.005"):
                    check_boll_resistance_signal = True
                else:
                    check_boll_resistance_signal = False
                all_signals_dict["check_boll_resistance_signal"] = check_boll_resistance_signal

                if self.macd_list_4h[0].macd <= self.macd_list_4h[1].macd:
                    check_macd_4h_signal = True
                else:
                    check_macd_4h_signal = False
                all_signals_dict["check_macd_4h_signal"] = check_macd_4h_signal

                if (self.kdj_list_4h[0].k_val < self.kdj_list_4h[1].k_val) \
                        and (self.kdj_list_4h[0].j_val < self.kdj_list_4h[1].j_val):
                    check_kdj_4h_signal = True
                else:
                    check_kdj_4h_signal = False
                all_signals_dict["check_kdj_4h_signal"] = check_kdj_4h_signal

                check_fng_signal = self.get_fng_signal(buy=True)
                if check_fng_signal is not None:
                    all_signals_dict["check_fng_signal"] = check_fng_signal

                if any(list(all_signals_dict.values())) is not True:
                    return

                signal_status = self.get_signal_count_status(*all_signals_dict.values())

                direction = f" 🔴 短线高频交易(策略待优化): 📉 卖出信号, " \
                            f"<br>总体信号-<b>{signal_status}</b>" \
                            f"<br>辅助信号-MACD趋势止升: {check_trend_stalled_signal}" \
                            f"<br>辅助信号-前最高价受阻: {check_price_resistance_signal}" \
                            f"<br>辅助信号-BOLL上轨价格回落: {check_boll_resistance_signal}" \
                            f"<br>辅助信号-4小时MACD下降：{check_macd_4h_signal}" \
                            f"<br>辅助信号-4小时KDJ下降：{check_kdj_4h_signal}" \
                            f"<br>总信号：{all_signals_dict}" \
                            f"<br>持仓时间：{hours_diff}"

        else:
            return

        email_msg_md5_str = (
            f"plotGpt:short_term_strategy:{self.symbol}:{current_kdj_1h.open_ts}"
        )
        email_msg_md5 = hashlib.md5(email_msg_md5_str.encode("utf8")).hexdigest()
        try:
            return EmailMsgHistoryTable.get(
                EmailMsgHistoryTable.msg_md5 == email_msg_md5
            )
        except EmailMsgHistoryTable.DoesNotExist:
            self.result[self.symbol] = self.short_term_strategy_reformat_notice(
                direction, current_kdj_1h, current_price, int(time.time()), close_monitor_url, set_limit_price_url)

        email_content = "".join(self.result.values())
        EmailMsgHistoryTable.create(msg_md5=email_msg_md5, msg_content=email_content)

        logger.info(
            f"PlotGptHandle.short_term_strategy finish, start end_msg, symbol:{self.symbol}, ts:{int(time.time())}")
        await self.send_msg(self.email_title, email_content)

    async def bull_run_strategy(self):
        """
        牛市大涨策略：
            主要工具：4小时K线图
        📈 买入信号
            1. 1小时MACD上行，DIF突破DEA。
            2. 4小时KDJ最近3根线持续上行，J值大于D值。(或 4小时KDJ最近3根线有金叉)
            3. 4小时k线：最近3条的最高价逐步递增，初步判断趋势大涨。
        """
        if self.macd_list_1h[0].macd < 0:
            return
        current_price = self.macd_list_1h[0].closing_price

        kdj_4h_up_signal = False
        for row in self.kdj_list_4h[:3]:
            if row.j_val < row.d_val:
                break
            kdj_4h_up_signal = True

        crossovers_data = analyze_crossovers(self.kdj_list_4h[:3])
        if crossovers_data["golden_cross"] > 0:
            kdj_4h_cross_signal = True
        else:
            kdj_4h_cross_signal = False

        if (kdj_4h_up_signal | kdj_4h_cross_signal) is False:
            return

        last_high_price = None
        open_ts = None
        for row in self.kline_list_4h[:3]:
            if last_high_price and last_high_price < row.high_price:
                return
            last_high_price = row.high_price

            if not open_ts:
                open_ts = row.open_ts

        current_ts = int(time.time())
        email_msg_md5_str = (
            f"plotGpt:bull_run_strategy:{self.symbol}:{open_ts}"
        )
        email_msg_md5 = hashlib.md5(email_msg_md5_str.encode("utf8")).hexdigest()
        try:
            return EmailMsgHistoryTable.get(
                EmailMsgHistoryTable.msg_md5 == email_msg_md5
            )
        except EmailMsgHistoryTable.DoesNotExist:
            close_monitor_url = f"{INNER_GET_DELETE_LIMIT_PRICE_URL}{self.symbol}"
            set_limit_price_url = f"{INNER_GET_SUBMIT_LIMIT_PRICE_URL}?" \
                                  f"symbol={self.symbol}&low_price={current_price*Decimal('0.988')}" \
                                  f"&high_price={current_price*Decimal('1.012')}"
            send_ts = int(time.time())

            self.result[self.symbol] = self.bull_run_strategy_reformat_notice(
                open_ts, current_price, send_ts, close_monitor_url, set_limit_price_url)

        email_content = "".join(self.result.values())
        EmailMsgHistoryTable.create(msg_md5=email_msg_md5, msg_content=email_content)

        logger.info(
            f"PlotGptHandle.bull_run_strategy finish, start end_msg, symbol:{self.symbol}, ts:{current_ts}")
        await self.send_msg(self.email_title, email_content)
