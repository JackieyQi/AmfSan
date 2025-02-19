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

from cache.order import MarketPriceLimitCache
from models.market import KlineTable
from models.order import MacdTable, KdjTable
from models.user import EmailMsgHistoryTable
from settings.constants import PLOT_INTERVAL_CONFIG, INNER_GET_DELETE_LIMIT_PRICE_URL, INNER_GET_SUBMIT_LIMIT_PRICE_URL
from utils.common import ts2bjfmt
from utils.indicators import analyze_list_trend, calculate_bollinger_bands, calculate_cv
from utils.templates import template_gpt_plot_trend_following_strategy_notice, \
    template_gpt_plot_short_term_strategy_notice, template_gpt_plot_bull_run_strategy_notice
from .base import BasePlotHandle

logger = logging.getLogger(__name__)


class PlotGptHandle(BasePlotHandle):
    def __init__(self, symbol):
        super().__init__()
        self.symbol = symbol
        self.email_title = f"{symbol} GPT Plot Notice"

        if "1h" not in PLOT_INTERVAL_CONFIG:
            raise Exception("Interval 1h miss.")
        if "4h" not in PLOT_INTERVAL_CONFIG:
            raise Exception("Interval 4h miss.")
        if "1d" not in PLOT_INTERVAL_CONFIG:
            raise Exception("Interval 1d miss.")

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
        query = (
            MacdTable.select().where(
                MacdTable.symbol == self.symbol,
                MacdTable.interval_val == interval,
            ).order_by(MacdTable.id.desc()).limit(27)
        )
        close_prices_list, ema_list = [], []
        for i, row in enumerate(query):
            if i == 0:
                # current_close_price = row.closing_price
                continue
            close_prices_list.append(row.closing_price)
            ema_list.append(row.ema_26)

        last_higher_band, last_lower_band = calculate_bollinger_bands(close_prices_list[::-1], ema_list[::-1])
        return last_higher_band, last_lower_band

    def trend_following_strategy_reformat_notice(self, direction, current_data):
        return template_gpt_plot_trend_following_strategy_notice(self.symbol, direction, current_data.open_ts)

    def short_term_strategy_reformat_notice(self, direction, current_kdj_1h, close_monitor_url, set_limit_price_url):
        return template_gpt_plot_short_term_strategy_notice(
            self.symbol, direction, current_kdj_1h.open_ts, close_monitor_url, set_limit_price_url)

    def bull_run_strategy_reformat_notice(self, current_ts):
        return template_gpt_plot_bull_run_strategy_notice(self.symbol, current_ts)

    async def check(self, limit_count=7):

        macd_list_1d, macd_list_4h, macd_list_1h = None, None, None
        for interval in ["1d", "4h", "1h"]:
            query = (
                MacdTable.select().where(
                    MacdTable.symbol == self.symbol,
                    MacdTable.interval_val == interval,
                ).order_by(MacdTable.id.desc()).limit(limit_count)
            )
            macd_list = [i for i in query]
            if not macd_list:
                return
            if len(macd_list) < limit_count:
                return

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

            if interval == "1d":
                macd_list_1d = macd_list
            elif interval == "4h":
                macd_list_4h = macd_list
            elif interval == "1h":
                macd_list_1h = macd_list

        # await self.trend_following_strategy(macd_list_1d, macd_list_4h, limit_count)
        await self.short_term_strategy(macd_list_1d, macd_list_4h, macd_list_1h, limit_count)
        # await self.short_term_strategy2(macd_list_4h, macd_list_1h, limit_count)
        await self.bull_run_strategy(macd_list_4h, macd_list_1h)

    async def trend_following_strategy(self, macd_list_1d, macd_list_4h, limit_count):
        """
        趋势跟随策略
            主要工具：MACD（跟踪趋势） + 日线/4小时线（确认趋势） + 1小时线（寻找买卖点）
        📈 买入信号
            1. 日线、4小时线的MACD金叉：DIF向上突破DEA，说明大方向上涨。
            2. 1小时线的MACD：不考虑，滞后性太高。
            3. KDJ确认超卖位置：当1小时KDJ处于20以下，且出现金叉信号时，进一步确认买入信号。
        📉 卖出信号
            1. 日线、4小时线的MACD：趋势向上，DIF向上突破DEA。
            2. KDJ确认超买位置：当1小时KDJ均处于80以上，当前J值小于前一个J值。
        ⚠️ 注意：当日线和4小时的趋势向上，但1小时出现反向信号时，可能是短期回调，不一定是大趋势的反转。
        """

        if macd_list_1d[0].macd < 0 or macd_list_4h[0].macd < 0:
            return

        interval = "1h"
        query = (
            KdjTable.select().where(
                KdjTable.symbol == self.symbol,
                KdjTable.interval_val == interval,
            ).order_by(KdjTable.id.desc()).limit(limit_count)
        )
        query_list = [i for i in query]
        if not query_list:
            return
        elif len(query_list) < limit_count:
            return

        current_data, last_data = query_list[0], query_list[1]

        now_ts = int(time.time())
        interval_sec = PLOT_INTERVAL_CONFIG[interval]["interval_sec"]
        if current_data.open_ts < (now_ts - interval_sec * 7):
            self.result[
                self.symbol
            ] = f"""
                    <br><a>Error: no lastest kdj data, {self.symbol}:{interval}</a>
                    <br><a>open_ts:{ts2bjfmt(current_data.open_ts)}</a>
                    <br><a>now_ts:{ts2bjfmt(now_ts)}</a>
                    """

            return await self.send_msg(self.email_title, "".join(self.result.values()))

        if current_data.k_val < Decimal("20") \
                and current_data.d_val < Decimal("20") and current_data.j_val < Decimal("20"):
            direction = "📈 买入信号"

        elif current_data.k_val > Decimal("80") \
                and current_data.d_val > Decimal("80") and current_data.j_val > Decimal("80"):
            if current_data.j_val >= last_data.j_val:
                return
            if not MarketPriceLimitCache.hget(self.symbol):
                return
            direction = "📉 卖出信号"

        else:
            return

        email_msg_md5_str = (
            f"plotGpt:trend_following_strategy:{self.symbol}:{current_data.open_ts}"
        )
        email_msg_md5 = hashlib.md5(email_msg_md5_str.encode("utf8")).hexdigest()
        try:
            return EmailMsgHistoryTable.get(
                EmailMsgHistoryTable.msg_md5 == email_msg_md5
            )
        except EmailMsgHistoryTable.DoesNotExist:
            self.result[self.symbol] = self.trend_following_strategy_reformat_notice(direction, current_data)

        email_content = "".join(self.result.values())
        EmailMsgHistoryTable.create(msg_md5=email_msg_md5, msg_content=email_content)

        logger.info(
            f"PlotGptHandle.trend_following_strategy finish, start end_msg, symbol:{self.symbol}, ts:{int(time.time())}")
        # TODO: receiver_list need optimized
        await self.send_msg(self.email_title, email_content,
                            receiver_list=["wayley@live.com", "358379803@qq.com", "bluekarl0220@gmail.com"])

    def get_signal_count_status(self, *args):
        true_count = sum([*args])
        false_count = len([*args]) - true_count

        if true_count > false_count:
            return "增强"
        elif true_count < false_count:
            return "减弱"
        else:
            return "持衡"

    async def short_term_strategy(self, macd_list_1d, macd_list_4h, macd_list_1h, limit_count):
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

            3. 1小时KDJ的J值在80附近，表示超买出现，开始考虑出场。
                3.1. 1小时MACD的当前时间段的值处于金叉，表示持续上涨，考虑持仓观望。
                   -> 3.1.1. (或)1小时MACD：最近7根线MACD柱状图的上行趋势减弱，表示上涨趋势减缓，表示出场信号加强。
                   -> 3.1.2. (或)当前1小时最高价，小于前面3根1小时线的最高价，表示价格受阻，超买回调趋势加强，表示出场信号加强。
        ⚠️ 注意：快进快出策略适合高频短线交易者，如果在趋势不明朗的震荡行情中，信号可能会频繁“假死叉”和“假金叉”。
        """
        if macd_list_1d[0].macd < 0 and macd_list_4h[0].macd < 0:
            return
        current_price = macd_list_1h[0].closing_price

        query = (
            KdjTable.select().where(
                KdjTable.symbol == self.symbol,
                KdjTable.interval_val == "1h",
            ).order_by(KdjTable.id.desc()).limit(limit_count)
        )
        query_list = [i for i in query]
        if not query_list:
            return
        elif len(query_list) < limit_count:
            return

        current_kdj_1h = query_list[0]
        latest_kdj_1h_list = query_list[:3]

        close_monitor_url = f"{INNER_GET_DELETE_LIMIT_PRICE_URL}{self.symbol}"
        set_limit_price_url = ""

        if not self.has_limit_price_check():
            query = (
                KdjTable.select().where(
                    KdjTable.symbol == self.symbol,
                    KdjTable.interval_val == "1d",
                ).order_by(KdjTable.id.desc()).limit(limit_count)
            )
            query_list = [i for i in query]
            if (query_list[0].j_val < query_list[0].d_val) and (query_list[1].j_val > query_list[1].d_val):
                return

            if current_kdj_1h.k_val > Decimal("35") \
                    or current_kdj_1h.d_val > Decimal("35") or current_kdj_1h.j_val > Decimal("35"):
                return

            current_trend_macd_1h, _ = analyze_list_trend([i.macd for i in macd_list_1h][::-1])
            if current_trend_macd_1h in ["downward_spiral", ]:
                return

            kline_1h_query = KlineTable.select().where(
                KlineTable.symbol == self.symbol,
                KlineTable.interval_val == "1h",
            ).order_by(KlineTable.id.desc()).limit(11)
            kline_1h_query_list = [i for i in kline_1h_query]
            current_1h_low_price = kline_1h_query_list[0].low_price
            last_1h_low_price = min([i.low_price for i in kline_1h_query_list[1:]])
            if current_1h_low_price < last_1h_low_price:
                return

            resistance_level, support_level = self.get_support_resistance_level("4h")
            check_price_fall_signal = current_price > support_level

            check_cv_cross_signal = False
            for _kdj in query_list[:3]:
                _cv = calculate_cv([_kdj.k_val, _kdj.d_val, _kdj.j_val])
                if _cv == 0:
                    check_cv_cross_signal = True
                    break

            query = KlineTable.select().where(
                KlineTable.symbol == self.symbol,
                KlineTable.interval_val == "4h",
            ).order_by(KlineTable.id.desc()).limit(4)
            kline_4h_query_list = [i for i in query]

            check_kdj_20_signal = False
            high_prices_4h_list = [i.high_price for i in kline_4h_query_list[:3]]
            if all(x < y for x, y in zip(high_prices_4h_list, high_prices_4h_list[1:])) is True:
                if current_kdj_1h.k_val < Decimal("20") and current_kdj_1h.d_val < Decimal("20") \
                        and current_kdj_1h.j_val < Decimal("20"):
                    check_kdj_20_signal = True

            volume_4h_list = [i.volume for i in kline_4h_query_list[1:]]
            last_mean_4h_volume = sum(volume_4h_list) / Decimal(len(kline_4h_query_list[1:]))
            current_4h_volume = kline_4h_query_list[0].volume
            volume_1h_list = [i.volume for i in kline_1h_query_list[1:]]
            last_mean_1h_volume = sum(volume_1h_list) / Decimal(len(kline_1h_query_list[1:]))
            current_1h_volume = kline_1h_query_list[0].volume
            if current_4h_volume > last_mean_4h_volume:
                check_4h_volume_up_signal = True
            else:
                check_4h_volume_up_signal = False

            if current_1h_volume > last_mean_1h_volume:
                check_1h_volume_up_signal = True
            else:
                check_1h_volume_up_signal = False

            if (check_price_fall_signal | check_cv_cross_signal | check_kdj_20_signal
                | check_4h_volume_up_signal | check_1h_volume_up_signal) \
                    is False:
                return

            signal_status = self.get_signal_count_status(
                check_price_fall_signal, check_cv_cross_signal, check_kdj_20_signal,
                check_4h_volume_up_signal, check_1h_volume_up_signal
            )

            direction = f" 🟢 短线高频交易(策略待优化): 📈 买入信号, " \
                        f"<br>总体信号-<b>{signal_status}</b>" \
                        f"<br>建议支撑位:{support_level}, 建议阻力位:{resistance_level}， " \
                        f"<br>辅助信号：价格未击穿支撑位: {check_price_fall_signal}, " \
                        f"<br>辅助信号：1小时KDJ有交叉: {check_cv_cross_signal}, " \
                        f"<br>辅助信号：1小时KDJ超卖: {check_kdj_20_signal}, " \
                        f"<br>辅助信号：1小时交易量流入增加：{check_1h_volume_up_signal}, " \
                        f"<br>辅助信号：4小时交易量流入增加：{check_4h_volume_up_signal},"

            set_limit_price_url = f"{INNER_GET_SUBMIT_LIMIT_PRICE_URL}?" \
                                  f"symbol={self.symbol}&low_price={support_level}&high_price={resistance_level}"

        elif MarketPriceLimitCache.hget(self.symbol):
            # TODO: 有的时候出场太早，趋势还在上涨。
            if current_kdj_1h.j_val <= Decimal("80"):
                for _kdj in latest_kdj_1h_list:
                    if _kdj.j_val >= Decimal("50"):
                        return

                direction = f" 🔴⚠️🔴短线高频交易(策略待优化): 📉 卖出信号, \n\n\b<br>上涨受阻，挂卖单在买入价->⌛️等待卖出！"

            else:
                if macd_list_1h[1].macd < 0 and macd_list_1h[0].macd >= 0:
                    return

                current_trend_macd_1h, _ = analyze_list_trend([i.macd for i in macd_list_1h][::-1])
                check_trend_stalled = current_trend_macd_1h not in ["parabolic_move", ]

                query = KlineTable.select().where(
                    KlineTable.symbol == self.symbol,
                    KlineTable.interval_val == "1h",
                ).order_by(KlineTable.id.desc()).limit(4)
                high_prices_list = [i.high_price for i in query]
                check_price_resistance = high_prices_list[0] < max(high_prices_list[1:])

                if (check_trend_stalled | check_price_resistance) is False:
                    return

                direction = f" 🔴 短线高频交易(策略待优化): 📉 卖出信号, " \
                            f"\n辅助信号-MACD趋势止升: {check_trend_stalled}" \
                            f"\n辅助信号-前最高价受阻: {check_price_resistance}"

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
                direction, current_kdj_1h, close_monitor_url, set_limit_price_url)

        email_content = "".join(self.result.values())
        EmailMsgHistoryTable.create(msg_md5=email_msg_md5, msg_content=email_content)

        logger.info(
            f"PlotGptHandle.short_term_strategy finish, start end_msg, symbol:{self.symbol}, ts:{int(time.time())}")
        await self.send_msg(self.email_title, email_content)

    async def short_term_strategy2(self, macd_list_4h, macd_list_1h, limit_count):
        """
        短线快进快出策略
            主要工具：4小时MACD+1小时KDJ+1小时MACD
        📈 买入信号
            1. 4小时MACD：零轴下方DIF上穿DEA，MACD柱状图逐步放大，趋势上行。
            2. 4小时交易量：当前4小时线的交易量 > 上一条4小时线的交易量的1.5~2倍。
            3. 1小时交易量：当前1小时交易量 > 上一条1小时交易量的1.5~2倍; 3根1小时线的平均交易量 > 前3根1小时线的平均交易量的1.5~2倍。
            4. 1小时线KDJ值均小于40，J值持续走平或向上；结合4小时布林带下轨支撑位，避免低位钝化。



        📉 卖出信号
        #     1. 1小时KDJ的K线下穿D线（死叉），且KDJ在80附近，表示超买回调。
        #     2. 1小时MACD死叉：DIF下穿DEA，短期下跌信号确认。
        ⚠️ 注意：快进快出策略适合高频短线交易者，如果在趋势不明朗的震荡行情中，信号可能会频繁“假死叉”和“假金叉”。
        """

        current_dea_4h = macd_list_4h[0].dea
        current_macd_4h = macd_list_4h[0].macd
        current_dif_4h = current_dea_4h + current_macd_4h
        if current_dif_4h > 0 or current_dea_4h > 0 or current_macd_4h < 0:
            return

        trend_str, _ = analyze_list_trend([i.macd for i in macd_list_4h][::-1])
        if trend_str not in ["parabolic_move", "modest_increase"]:
            return

        query = KlineTable.select().where(
            KlineTable.symbol == self.symbol,
            KlineTable.interval_val == "4h",
            # KlineTable.open_ts <= macd_list_4h[0].opening_ts,
        ).order_by(KlineTable.id.desc()).limit(2)
        current_kline_4h, last_kline_4h = query[0], query[1]

        if current_kline_4h.volume < Decimal("1.5") * last_kline_4h.volume:
            return

        query = KlineTable.select().where(
            KlineTable.symbol == self.symbol,
            KlineTable.interval_val == "1h",
            # KlineTable.open_ts <= macd_list_1h[0].opening_ts,
        ).order_by(KlineTable.id.desc()).limit(limit_count)
        volume_list = [i.volume for i in query]

        current_volume_1h = volume_list[0]
        last_volume_1h = volume_list[1]
        if current_volume_1h < Decimal("1.5") * last_volume_1h:
            return

        if sum(volume_list[:3]) / Decimal(len(volume_list[:3])) < \
                Decimal("1.5") * (sum(volume_list[3:]) / Decimal(len(volume_list[3:]))):
            return

        query = (
            KdjTable.select().where(
                KdjTable.symbol == self.symbol,
                KdjTable.interval_val == "1h",
            ).order_by(KdjTable.id.desc()).limit(limit_count)
        )
        query_list = [i for i in query]
        if not query_list:
            return
        elif len(query_list) < limit_count:
            return

        current_kdj_1h = query_list[0]
        if current_kdj_1h.k_val < Decimal("40") \
                and current_kdj_1h.d_val < Decimal("40") and current_kdj_1h.j_val < Decimal("40"):
            direction = "short_term_strategy2: 📈 买入信号"
        # TODO: 卖出信号
        else:
            return

        query = (
            MacdTable.select().where(
                MacdTable.symbol == self.symbol,
                MacdTable.interval_val == "4h",
            ).order_by(MacdTable.id.desc()).limit(27)
        )
        close_prices_list, ema_list = [], []
        current_close_price = Decimal("0")
        for i, row in enumerate(query):
            if i == 0:
                current_close_price = row.closing_price
                continue
            close_prices_list.append(row.closing_price)
            ema_list.append(row.ema_26)

        _, last_lower_band = calculate_bollinger_bands(close_prices_list[::-1], ema_list[::-1])
        if current_close_price > last_lower_band:
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
            self.result[self.symbol] = self.short_term_strategy_reformat_notice(direction, current_kdj_1h)

        email_content = "".join(self.result.values())
        EmailMsgHistoryTable.create(msg_md5=email_msg_md5, msg_content=email_content)

        logger.info(
            f"PlotGptHandle.short_term_strategy finish, start end_msg, symbol:{self.symbol}, ts:{int(time.time())}")
        await self.send_msg(self.email_title, email_content)

    async def bull_run_strategy(self, macd_list_4h, macd_list_1h):
        """
        牛市大涨策略：
            主要工具：4小时K线图
        📈 买入信号
            # 1. 4小时MACD上行，DIF突破DEA。
            1. 1小时MACD上行，DIF突破DEA。
            2. 4小时KDJ上行，J值大于D值。
            3. 4小时k线：最近3条的最高价逐步递增，初步判断趋势大涨。
        """
        if macd_list_1h[0].macd < 0:
            return

        query = (
            KdjTable.select().where(
                KdjTable.symbol == self.symbol,
                KdjTable.interval_val == "4h",
            ).order_by(KdjTable.id.desc()).limit(3)
        )
        for row in query:
            if row.j_val < row.d_val:
                return

        query = KlineTable.select().where(
            KlineTable.symbol == self.symbol,
            KlineTable.interval_val == "4h",
        ).order_by(KlineTable.id.desc()).limit(3)
        last_high_price = None
        open_ts = None
        for row in query:
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
            self.result[self.symbol] = self.bull_run_strategy_reformat_notice(open_ts)

        email_content = "".join(self.result.values())
        EmailMsgHistoryTable.create(msg_md5=email_msg_md5, msg_content=email_content)

        logger.info(
            f"PlotGptHandle.bull_run_strategy finish, start end_msg, symbol:{self.symbol}, ts:{current_ts}")
        await self.send_msg(self.email_title, email_content)
