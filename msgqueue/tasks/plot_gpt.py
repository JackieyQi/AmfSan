#! /usr/bin/env python
# -*- coding: UTF-8 -*-
"""
🧠
| 特点 | 策略一：多因子打分 | 策略二：结构优先+条件打分 |
|------|--------------------|----------------------------|
| 灵活性 | 高，可动态加权 | 中等，依赖特定结构 |
| 可解释性 | 中等（需说明每个因子） | 强（结构清晰） |
| 胜率控制 | 可精细调参 | 靠结构识别精度 |
| 回测难度 | 适中 | 稍高（结构识别复杂） |
| 易错点 | 冗余因子、过拟合 | 结构识别不稳、主观性强 |

"""

import hashlib
import logging
import time
from decimal import Decimal

from exts import async_database
from cache import AllCache
from cache.order import MarketPriceLimitCache, FearAndGreedIndexCache
from models.market import KlineTable, MacdTable, KdjTable, RsiTable, BollTable
from models.order import PlotBackTestTable
from models.user import EmailMsgHistoryTable
from models.factor import CandlestickFactor, MacdFactor, KdjFactor, RsiFactor
from models.strategy import ModelBollMidRebound, ModelBollLowReboundBullishDown, ModelBollLowReboundBullishSideways, \
    ModelLTypeRebound, ModelWTypeRebound, ModelVTypeRebound
from settings.constants import PLOT_INTERVAL_CONFIG, INNER_GET_DELETE_LIMIT_PRICE_URL, INNER_GET_SUBMIT_LIMIT_PRICE_URL
from utils.common import ts2bjfmt, decimal2decimal, decimal2str
from utils.hrequest import http_get_request
from utils.indicators import check_near_low, get_atr_price, check_near_high
from utils.templates import template_gpt_plot_trend_following_strategy_notice, \
    template_gpt_plot_short_term_strategy_notice, template_gpt_plot_bull_run_strategy_notice, template_strategy_notice
from business.back_test import BackTestHandler
from .base import BasePlotHandle

logger = logging.getLogger(__name__)


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
        self.bb_list_1h = None
        self.bb_list_4h = None

        required_intervals = ["1h", "4h", "1d"]
        for interval in required_intervals:
            if interval not in PLOT_INTERVAL_CONFIG:
                raise ValueError(f"Required interval {interval} is missing in configuration")

    async def initialize_indicators(self):
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

            _query = self.get_kdj_query("4h", limit_count=30)
            _kdj_list_4h = await _query.aio_execute()
            self._kdj_list_4h = list(_kdj_list_4h)

            _query = self.get_kdj_query("1h", limit_count=30)
            _kdj_list_1h = await _query.aio_execute()
            self._kdj_list_1h = list(_kdj_list_1h)

            _query = self.get_rsi_query("1h", limit_count=30)
            _rsi_list_1h = await _query.aio_execute()
            self.rsi_list_1h = list(_rsi_list_1h)

            _query = self.get_rsi_query("4h", limit_count=30)
            _rsi_list_4h = await _query.aio_execute()
            self.rsi_list_4h = list(_rsi_list_4h)

            _query = self.get_bb_query("1h", limit_count=30)
            _bb_list_1h = await _query.aio_execute()
            self.bb_list_1h = list(_bb_list_1h)

            _query = self.get_bb_query("4h", limit_count=30)
            _bb_list_4h = await _query.aio_execute()
            self.bb_list_4h = list(_bb_list_4h)

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
            RsiTable.select(RsiTable.rsi, RsiTable.open_ts).where(
                RsiTable.symbol == self.symbol,
                RsiTable.interval_val == interval,
            ).order_by(RsiTable.id.desc()).limit(limit_count)
        )
        return query

    def get_bb_query(self, interval, limit_count=18):
        query = (
            BollTable.select(BollTable.bbupper, BollTable.bbmid, BollTable.bblower, BollTable.open_ts).where(
                BollTable.symbol == self.symbol,
                BollTable.interval_val == interval,
            ).order_by(BollTable.id.desc()).limit(limit_count)
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
        self.prompt_text += f"\n<br> 计算建议价：当前价格:{current_price}，根据最新99条深度数据，最大挂买单量的价格:{bid_price}，按照买入建议价公式：bid_price + (current_price - bid_price) * Decimal('0.6')，得到买入建议价:{decimal2str(recommend_bid_price)}；" \
                            f"最大挂卖单量的价格:{ask_price}，按照卖出建议价的公式：current_price + (ask_price - current_price) * Decimal('0.6')，得到卖出建议价：{decimal2str(recommend_ask_price)}。你有更好的买入或者卖出建议价吗"
        return {
            "bid_price": bid_price,
            "ask_price": ask_price,
            "recommend_bid_price": decimal2decimal(recommend_bid_price),
            "recommend_ask_price": decimal2decimal(recommend_ask_price),
        }

    def get_recommend_price(self, curr_price):
        depth_prices_data = self.get_depth_prices(curr_price)
        most_bid_price = depth_prices_data["bid_price"]
        most_ask_price = depth_prices_data["ask_price"]

        atr_window_size = 6
        atr_price_info = get_atr_price(
            self.kline_list_1h[:atr_window_size+1][::-1], curr_price, window_size=atr_window_size)
        sl_price = decimal2decimal(atr_price_info["sl_price"])
        tp_price = decimal2decimal(atr_price_info["tp_price"])

        recommend_bid_price = (most_bid_price + sl_price + curr_price)/Decimal("3")
        if recommend_bid_price > self.bb_list_1h[0].bbupper:
            recommend_bid_price = self.bb_list_1h[0].bbupper

        recommend_ask_price = (most_ask_price + tp_price + curr_price)/Decimal("3")
        if recommend_ask_price > self.bb_list_1h[0].bbupper:
            recommend_ask_price = self.bb_list_1h[0].bbupper

        return {
            "sl_price": sl_price,
            "tp_price": tp_price,
            "recommend_bid_price": decimal2decimal(recommend_bid_price),
            "recommend_ask_price": decimal2decimal(recommend_ask_price),
        }

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
        await self.initialize_indicators()

        if not self.kline_list_1h:
            return
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
            strategy_text = ""
            recommend_bid_price = None

            if model_info := await self.get_buy_by_model_detect(curr_price):
                recommend_bid_price = model_info["recommend_bid_price"]
                strategy_text += model_info["model_name"]

            elif score_info := await self.get_buy_by_multi_factor_score(curr_price):
                for k, v in score_info.items():
                    strategy_text += f"{k}:{v}分;"

            else:
                return

            recommend_price_data = self.get_recommend_price(curr_price)
            recommend_bid_price = recommend_bid_price or recommend_price_data["recommend_bid_price"]
            recommend_sl_price = recommend_price_data["sl_price"]
            recommend_tp_price = recommend_price_data["tp_price"]

            self.set_limit_price_url = f"{INNER_GET_SUBMIT_LIMIT_PRICE_URL}?" \
                                       f"symbol={self.symbol}" \
                                       f"&low_price={recommend_sl_price}" \
                                       f"&high_price={recommend_tp_price}"

            redis_client = AllCache.get_client()
            redis_client.set(f"sl_tp:{self.symbol}", f"{recommend_sl_price}:{recommend_tp_price}")

            direction = f"<br> 🟢 短线买入信号: <b>{self.symbol.upper()}</b>" \
                        f"\n<br> 总分: {sum(score_info.values())}。" \
                        f"\n<br> 策略详情： {strategy_text}。" \
                        f"\n<br><br> 📈 建议买入价: {decimal2str(recommend_bid_price)}，" \
                        f"当前价: {decimal2str(curr_price)}。<br><br>"
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
                # redis_client = AllCache.get_client()
                # cache_data = redis_client.get(f"sl_tp:{self.symbol}")
                # if not cache_data:
                #     return

                func_str = "tp_sl"
                limit_price = MarketPriceLimitCache.hget(self.symbol)
                set_time, limit_low_price, limit_high_price = limit_price.split(":")

                sl_price, tp_price = map(Decimal, (limit_low_price, limit_high_price))

                if curr_price >= tp_price:
                    part_direction += "当前价格触及止盈价，止盈离场。"
                    recommend_ask_price = curr_price
                    ask_plot_type = 8
                elif curr_price <= min(sl_price, self.bb_list_1h[0].bblower):
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
                        f"<br><br> 📉 建议卖出价：{decimal2str(recommend_ask_price)}，" \
                        f"当前价: {decimal2str(curr_price)}。" \

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
            direction, open_ts, decimal2str(curr_price),
            self.check_time, self.close_monitor_url, self.set_limit_price_url)

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

    def is_bb_lower2mid_taking_profit(self):
        """
        价格从下轨到达中轨，优先止盈
        """
        kline_1h_factors = CandlestickFactor(self.kline_list_1h, self.macd_list_1h, self.bb_list_1h)

        if self.kline_list_1h[2].high_price < self.bb_list_1h[2].bbmid \
                and not kline_1h_factors.is_near_mid(index=2, tolerance=Decimal("0.2")):
            if kline_1h_factors.is_near_mid(index=1, tolerance=Decimal("0.2")):
                if self.macd_list_1h[0].macd < 0 or self.kdj_list_1h[0].j_val > 80 or (self.rsi_list_1h[0].rsi < Decimal("75")):
                    return True
            return False

    def _get_sell_direction_active_taking_profit(self, curr_price):
        """
        主动止盈:
            * 若 KDJ J 值 > 90 且 MACD DIF 下降，视为强势过热信号，部分止盈。
            * 1小时的RSI > 80 + 当前价格接近或突破布林带上轨 + 成交量放大 -> 止盈离场。

            * 价格逼近 1小时布林带上轨：
                    1. 如果 RSI < 75 且 MACD 柱状图收缩（即动能减弱）→ 执行止盈
                    TODO: 2. 如果 RSI > 75 且 KDJ 仍金叉、MACD 扩张 → 等待下一根 K 线确认
                    TODO: 3. 如果连续3根K线都在上轨附近但价格未放量上涨 → 止盈

            TODO:* 前k的最高价突破中轨 + 当前k为十字线时，触发卖出。
        :return:
        """
        direction = ""
        macd_1h_factors = MacdFactor(self.macd_list_1h)

        if self.kdj_list_1h[0].j_val > 90 and macd_1h_factors.get_dif_downtrend():
            direction += "强势过热信号，部分止盈。"
            return {"direction": direction}

        kline_1h_factors = CandlestickFactor(self.kline_list_1h, self.macd_list_1h, self.bb_list_1h)
        if self.rsi_list_1h[0].rsi > Decimal("80") and kline_1h_factors.is_near_upper() \
                and kline_1h_factors.get_vol_factor(5).get("has_enhance_spike_volume", False):
            direction += "止盈离场：1小时的RSI > 80 + 当前价格接近或突破布林带上轨 + 成交量放大"
            return {"direction": direction}

        near_info = check_near_high(self.kline_list_1h[:21][::-1], self.bb_list_1h[0].bbmid, self.bb_list_1h[0].bbupper, logger)
        if near_info["is_near"]:
            if (self.rsi_list_1h[0].rsi < Decimal("75")) and (self.macd_list_1h[0].macd < self.macd_list_1h[1].macd):
                direction += "价格逼近 1小时布林带上轨，RSI < 75 且 MACD 柱状图收缩（即动能减弱），优先止盈。"
                return {"direction": direction, "recommend_ask_price": curr_price}

        if self.is_bb_lower2mid_taking_profit():
            direction += "价格 1小时布林带下轨抵达中轨，(macd<0)/(kdj.j>80)/(RSI<75)，优先止盈。"
            return {"direction": direction}

        if kline_1h_factors.has_double_top():
            direction += "当前处于1小时双顶形态，止盈离场。"
            return {"direction": direction}

        kline_4h_factors = CandlestickFactor(self.kline_list_4h, self.macd_list_4h, self.bb_list_4h)
        if kline_4h_factors.is_bearish_engulfing_k(index=1):
            direction += "4小时的前k线看跌吞没，止盈离场。"
            return {"direction": direction}

        return {"direction": direction} if direction else {}

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

        macd_4h_factors = MacdFactor(self.macd_list_4h)
        if macd_4h_factors.get_downtrend():
            score_info["macd_4h_downtrend"] = 10

        if (self.kdj_list_1h[0].j_val > 80) and (self.kdj_list_1h[0].j_val < self.kdj_list_1h[1].j_val):
            score_info["kdj_1h_j_80_downtrend"] = 10

        if (self.kdj_list_1d[0].k_val > 80) and (self.kdj_list_1d[0].d_val > 80) \
                and (self.kdj_list_1d[0].j_val < self.kdj_list_1d[1].j_val):
            score_info["kdj_1d_over_bought"] = 15

        if (self.kdj_list_4h[0].k_val > 80) and (self.kdj_list_4h[0].d_val > 80) \
                and (self.kdj_list_4h[0].j_val < self.kdj_list_4h[1].j_val):
            score_info["kdj_4h_over_bought"] = 15

        kline_1h_factors = CandlestickFactor(self.kline_list_1h, self.macd_list_1h, self.bb_list_1h)
        window = 3
        max_price = kline_1h_factors.get_donchian_channel(window_size=window)["max_price"]
        vol_1h_factor = kline_1h_factors.get_vol_factor(window, rate_threshold=Decimal("2"))
        if vol_1h_factor.get("has_enhance_spike_volume") and self.kline_list_1h[0].high_price < max_price:
            score_info["vol_1h_stagflation"] = 15

        sum_score = sum(score_info.values())
        if sum_score >= 20:
            score_detail_text = ""
            for k, v in score_info.items():
                score_detail_text += f"{k}:{v}分;"
            return score_detail_text
        return ""

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

    async def get_buy_by_multi_factor_score(self, current_price):
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

        if self.macd_list_1d[0].macd > 0:
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

        if sum_score >= 60:
            return score_info
        return {}

    def _get_adjust_score_boll_4h(self, score, curr_price, kline_4h_factors):
        curr_score_info = {}
        high_price = self.kline_list_4h[0].high_price
        open_price = self.kline_list_4h[0].open_price

        if (curr_price < self.bb_list_4h[0].bbupper) and (high_price > self.bb_list_4h[0].bbupper):
            score -= 3 # 最高价突破上轨但当前价低于上轨，可能是假突破 -> -3 分

        if (curr_price > self.bb_list_4h[0].bbupper) and (open_price > self.bb_list_4h[0].bbupper):
            score -= 3 # 开盘价突破上轨，当前价突破上轨，高开高走 -> -3 分

        if self.kline_list_4h[0].high_price > self.bb_list_4h[0].bbupper and kline_4h_factors.get_crosshairs():
            curr_score_info["overheat_4h_upper_crosshairs"] = -5 # 4小时的当前k线最高价突破上轨且为十字线 -> -5 分

        return score + sum(curr_score_info.values())

    def _get_adjust_score_boll_1h(self, score, curr_price, kline_1h_factors):
        curr_score_info = {}

        for index in (0, 1):
            if kline_1h_factors.get_long_upper_shadow(index) and kline_1h_factors.get_fake_breakout_by_bb(index):
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
        if kline_4h_factors.get_long_upper_shadow():
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
        if macd_factors.get_downtrend():
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

    async def get_buy_by_model_detect(self, curr_price):
        kline_1d_factors = CandlestickFactor(None, self.macd_list_1d, None)
        kline_4h_factors = CandlestickFactor(self.kline_list_4h, self.macd_list_4h, self.bb_list_4h)
        kline_1h_factors = CandlestickFactor(self.kline_list_1h, self.macd_list_1h, self.bb_list_1h)
        macd_4h_factors = MacdFactor(self.macd_list_4h)
        macd_1h_factors = MacdFactor(self.macd_list_1h)
        kdj_4h_factors = KdjFactor(self.kdj_list_4h)
        kdj_1h_factors = KdjFactor(self.kdj_list_1h)
        rsi_4h_factors = RsiFactor(self.rsi_list_4h)
        rsi_1h_factors = RsiFactor(self.rsi_list_1h)

        model_boll_mid_rebound = ModelBollMidRebound(curr_price)
        if model_boll_mid_rebound.is_detected(
                kline_4h_factors, kline_1h_factors, macd_4h_factors, kdj_1h_factors, rsi_1h_factors):
            model_recommend_price_data = model_boll_mid_rebound.get_recommend_price(self.kline_list_1h[0].low_price)
            return {"model_name": model_boll_mid_rebound.name, "recommend_bid_price": model_recommend_price_data["recommend_bid_price"]}

        model_b = ModelBollLowReboundBullishSideways(curr_price)
        if model_b.is_detected(
                kline_4h_factors, kline_1h_factors, macd_4h_factors, kdj_1h_factors, rsi_1h_factors):
            model_recommend_price_data = model_b.get_recommend_price(self.kline_list_1h, self.bb_list_1h)
            return {"model_name": model_b.name,
                    "recommend_bid_price": model_recommend_price_data["recommend_bid_price"]}

        model_c = ModelBollLowReboundBullishDown(curr_price)
        if model_c.is_detected(
                kline_4h_factors, kline_1h_factors, macd_4h_factors, kdj_1h_factors, rsi_1h_factors):
            model_recommend_price_data = model_c.get_recommend_price(kline_1h_factors)
            return {"model_name": model_c.name,
                    "recommend_bid_price": model_recommend_price_data["recommend_bid_price"]}

        model_d = ModelLTypeRebound(curr_price)
        if model_d.is_detected(kline_1d_factors, kline_4h_factors, kline_1h_factors, macd_4h_factors, kdj_1h_factors):
            model_recommend_price_data = model_d.get_recommend_price(self.bb_list_1h)
            return {"model_name": model_d.name,
                    "recommend_bid_price": model_recommend_price_data["recommend_bid_price"]}

        model_w = ModelWTypeRebound(curr_price)
        if model_w.is_detected(self.kline_list_4h, self.kline_list_1h, self.macd_list_4h, self.macd_list_1h,
                               self.bb_list_4h, self.bb_list_1h, self.rsi_list_4h, self.rsi_list_1h,
                               kline_4h_factors, macd_4h_factors):
            model_recommend_price_data = model_w.get_recommend_price(self.bb_list_1h)
            return {"model_name": model_w.name,
                    "recommend_bid_price": model_recommend_price_data["recommend_bid_price"]}

        model_v = ModelVTypeRebound(curr_price)
        if model_v.is_detected(self.kline_list_1h, self.bb_list_1h, kline_1h_factors, kdj_4h_factors):
            model_recommend_price_data = model_v.get_recommend_price(self.bb_list_1h)
            return {"model_name": model_v.name,
                    "recommend_bid_price": model_recommend_price_data["recommend_bid_price"]}

        return
