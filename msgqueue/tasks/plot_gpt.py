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
from settings.constants import PLOT_INTERVAL_CONFIG
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

    def short_term_strategy_reformat_notice(self, direction, current_kdj_1h):
        return template_gpt_plot_short_term_strategy_notice(self.symbol, direction, current_kdj_1h.open_ts)

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

        await self.trend_following_strategy(macd_list_1d, macd_list_4h, limit_count)
        await self.short_term_strategy(macd_list_1d, macd_list_4h, macd_list_1h, limit_count)
        await self.short_term_strategy2(macd_list_4h, macd_list_1h, limit_count)
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

    async def short_term_strategy(self, macd_list_1d, macd_list_4h, macd_list_1h, limit_count):
        """
        短线快进快出策略
            主要工具：1小时KDJ+4小时MACD/日线MACD
            触发条件：核心信号满足+任意一个辅助信号满足即可触发买入，这样可以避免因为条件过多而错失信号。
        📈 买入信号
            1. 4小时MACD上行：DIF上穿DEA；或者 日线MACD上行：DIF上穿DEA。
            2. 1小时KDJ的K线上穿D线（金叉），且KDJ在35附近，表示超卖反弹。
            3. 1小时MACD：最近7根线MACD柱状图的下行趋势减弱，表示下跌趋势减缓。
                3.1. (或)当前价格大于4小时布林带下轨值，未击穿支撑位，增强买入信号。
                3.2. (或)1小时KDJ的最近3条线，有接近死叉或金叉，增强信号。
                3.3. (或)4小时K线的近三条的最高价逐步下降，表示下跌压力依旧很大，1小时KDJ均值在20附近，提示买入信号。
        📉 卖出信号
            1. 4小时MACD上行：DIF上穿DEA；或者 日线MACD上行：DIF上穿DEA。
            2. 1小时KDJ的K线下穿D线（死叉），且J值在80附近，表示超买出现。
               -> 2-1. (或)1小时MACD：最近7根线MACD柱状图的上行趋势减弱，表示上涨趋势减缓。
               -> 2-2. (或)当前1小时最高价，小于前面3根1小时线的最高价，表示价格受阻，超买回调趋势加强。
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

        if not self.has_limit_price_check():
            # TODO: KDJ均值35设置过高，需要结合其他场景判断
            if current_kdj_1h.k_val < Decimal("35") \
                    and current_kdj_1h.d_val < Decimal("35") and current_kdj_1h.j_val < Decimal("35"):

                current_trend_macd_1h, _ = analyze_list_trend([i.macd for i in macd_list_1h][::-1])
                if current_trend_macd_1h in ["downward_spiral", ]:
                    return

                resistance_level, support_level = self.get_support_resistance_level("4h")
                check_price_fall = current_price > support_level

                check_cv_cross = False
                for _kdj in query_list[:3]:
                    _cv = calculate_cv([_kdj.k_val, _kdj.d_val, _kdj.j_val])
                    if _cv == 0:
                        check_cv_cross = True
                        break

                check_kdj_20 = False
                query = KlineTable.select().where(
                    KlineTable.symbol == self.symbol,
                    KlineTable.interval_val == "4h",
                ).order_by(KlineTable.id.desc()).limit(3)
                high_prices_4h_list = [i.high_price for i in query]
                if all(x < y for x, y in zip(high_prices_4h_list, high_prices_4h_list[1:])) is True:
                    if current_kdj_1h.k_val < Decimal("20") and current_kdj_1h.d_val < Decimal("20") \
                            and current_kdj_1h.j_val < Decimal("20"):
                        check_kdj_20 = True

                if (check_price_fall | check_cv_cross | check_kdj_20) is False:
                    return

                direction = f"⚠️短线高频交易(策略待优化): 📈 买入信号, " \
                            f"建议支撑位:{support_level}, 建议阻力位:{resistance_level}， " \
                            f"辅助信号：check_price_fall: {check_price_fall}, " \
                            f"辅助信号：check_cv_cross: {check_cv_cross}, " \
                            f"辅助信号：check_kdj_20: {check_kdj_20}"
            else:
                return

        elif MarketPriceLimitCache.hget(self.symbol):
            # TODO: 有的时候出场太早，趋势还在上涨。
            if current_kdj_1h.j_val > Decimal("80"):

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

                direction = f"⚠️短线高频交易(策略待优化): 📉 卖出信号, " \
                            f"辅助信号：check_trend_stalled: {check_trend_stalled}" \
                            f"辅助信号：check_price_resistance: {check_price_resistance}"
            else:
                return
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
            self.result[self.symbol] = self.short_term_strategy_reformat_notice(direction, current_kdj_1h)

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
