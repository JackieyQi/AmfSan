#! /usr/bin/env python
# -*- coding: UTF-8 -*-

import logging
import time
from decimal import Decimal

from exts import async_database
from cache import AllCache, check_rate_limit
from cache.order import MarketPriceLimitCache, FearAndGreedIndexCache
from models.market import KlineTable, MacdTable, KdjTable, RsiTable, BollTable
from models.order import PlotBackTestTable
from models.user import EmailMsgHistoryTable, UserSymbolPlotTable, UserInfoTable
from models.factor import CandlestickFactor, MacdFactor, KdjFactor, RsiFactor
from settings.constants import PLOT_INTERVAL_CONFIG, INNER_GET_DELETE_LIMIT_PRICE_URL, INNER_GET_SUBMIT_LIMIT_PRICE_URL
from utils.common import ts2bjfmt, decimal2decimal, decimal2str
from utils.hrequest import http_get_request
from utils.indicators import check_near_low, get_atr_price, check_near_high
from utils.templates import template_strategy_notice
from business.trade_signal_recorder import TradeSignalHandler
from business.strategy import StrategyHandle
from .base import BasePlotHandle

logger = logging.getLogger(__name__)


class StrategyCheckHandle(BasePlotHandle):
    def __init__(self, symbol):
        super().__init__()
        self.symbol = symbol
        self.check_time = int(time.time())
        self.email_title = f"{symbol} Strategy Check Notice"

        self.close_monitor_url = f"{INNER_GET_DELETE_LIMIT_PRICE_URL}{symbol}"
        self.set_limit_price_url = ""

        self._kline_list_4h = None
        self._kline_list_1h = None
        self.kline_list_15m = None
        
        self._macd_list_1d = None
        self._macd_list_4h = None
        self._macd_list_1h = None
        self.macd_list_15m = None
        
        self._kdj_list_1d = None
        self._kdj_list_4h = None
        self._kdj_list_1h = None
        self.kdj_list_15m = None

        self.rsi_list_1h = None
        self.rsi_list_4h = None
        self.rsi_list_15m = None

        self.bb_list_1h = None
        self.bb_list_4h = None
        self.bb_list_15m = None

    async def initialize_indicators(self):
        async with async_database.aio_atomic():
            _query = self.get_kline_query("4h", limit_count=30)
            _kline_list_4h = await _query.aio_execute()
            self._kline_list_4h = list(_kline_list_4h)

            _query = self.get_kline_query("1h", limit_count=30)
            _kline_list_1h = await _query.aio_execute()
            self._kline_list_1h = list(_kline_list_1h)

            _query = self.get_kline_query("15m", limit_count=30)
            _kline_list_15m = await _query.aio_execute()
            self.kline_list_15m = list(_kline_list_15m)

            _query = self.get_macd_query("1d", limit_count=30)
            _macd_list_1d = await _query.aio_execute()
            self._macd_list_1d = list(_macd_list_1d)

            _query = self.get_macd_query("4h", limit_count=30)
            _macd_list_4h = await _query.aio_execute()
            self._macd_list_4h = list(_macd_list_4h)

            _query = self.get_macd_query("1h", limit_count=30)
            _macd_list_1h = await _query.aio_execute()
            self._macd_list_1h = list(_macd_list_1h)

            _query = self.get_macd_query("15m", limit_count=30)
            _macd_list_15m = await _query.aio_execute()
            self.macd_list_15m = list(_macd_list_15m)

            _query = self.get_kdj_query("1d", limit_count=2)
            _kdj_list_1d = await _query.aio_execute()
            self._kdj_list_1d = list(_kdj_list_1d)

            _query = self.get_kdj_query("4h", limit_count=30)
            _kdj_list_4h = await _query.aio_execute()
            self._kdj_list_4h = list(_kdj_list_4h)

            _query = self.get_kdj_query("1h", limit_count=30)
            _kdj_list_1h = await _query.aio_execute()
            self._kdj_list_1h = list(_kdj_list_1h)

            _query = self.get_kdj_query("15m", limit_count=30)
            _kdj_list_15m = await _query.aio_execute()
            self.kdj_list_15m = list(_kdj_list_15m)

            _query = self.get_rsi_query("1h", limit_count=30)
            _rsi_list_1h = await _query.aio_execute()
            self.rsi_list_1h = list(_rsi_list_1h)

            _query = self.get_rsi_query("4h", limit_count=30)
            _rsi_list_4h = await _query.aio_execute()
            self.rsi_list_4h = list(_rsi_list_4h)

            _query = self.get_rsi_query("15m", limit_count=30)
            _rsi_list_15m = await _query.aio_execute()
            self.rsi_list_15m = list(_rsi_list_15m)

            _query = self.get_bb_query("1h", limit_count=30)
            _bb_list_1h = await _query.aio_execute()
            self.bb_list_1h = list(_bb_list_1h)

            _query = self.get_bb_query("4h", limit_count=30)
            _bb_list_4h = await _query.aio_execute()
            self.bb_list_4h = list(_bb_list_4h)

            _query = self.get_bb_query("15m", limit_count=30)
            _bb_list_15m = await _query.aio_execute()
            self.bb_list_15m = list(_bb_list_15m)

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

        if not self.kline_list_1h or not self.macd_list_1d:
            return
        open_ts = self.kline_list_1h[0].open_ts
        curr_price = self.kline_list_1h[0].close_price

        interval_sec = PLOT_INTERVAL_CONFIG["4h"]["interval_sec"]
        if self.macd_list_4h[0].opening_ts < (self.check_time - interval_sec * limit_count):
            if check_rate_limit("no_latest_macd_data", limit=3, expire=600):
                return

            self.result[
                self.symbol
            ] = f"""
                    <br><a>Error: no lastest macd data, {self.symbol}:4h</a>
                    <br><a>opening_ts:{ts2bjfmt(self.macd_list_4h[0].opening_ts)}</a>
                    <br><a>now_ts:{ts2bjfmt(self.check_time)}</a>
                    """

            return await self.send_msg(self.email_title, f"check_macd_list:{self.symbol}:{open_ts}")

        if not await self.has_limit_price_check((0, 1, 3)):
            logger.debug(f"strategy buy check start, symbol:{self.symbol}")

            strategy_text = ""
            score_info = {}
            recommend_bid_price = None

            strategy_handler = StrategyHandle(
                self.kline_list_4h, self.kline_list_1h, self.kline_list_15m,
                self.bb_list_4h, self.bb_list_1h, self.bb_list_15m,
                self.macd_list_1d, self.macd_list_4h, self.macd_list_1h, self.macd_list_15m,
                self.kdj_list_1d, self.kdj_list_4h, self.kdj_list_1h, self.kdj_list_15m,
                self.rsi_list_4h, self.rsi_list_1h, self.rsi_list_15m
            )
            try:
                history_orders = await PlotBackTestTable.select().where(
                    PlotBackTestTable.symbol == self.symbol,
                ).order_by(PlotBackTestTable.id.desc()).limit(2).aio_execute()
                last_model_msg = history_orders[0].ask_plot_msg if history_orders[0].ask_plot_msg else \
                    history_orders[0].bid_plot_msg
                if len(history_orders) > 1:
                    last_model_msg_2 = history_orders[1].ask_plot_msg if history_orders[1].ask_plot_msg else \
                        history_orders[1].bid_plot_msg
                else:
                    last_model_msg_2 = ""
            except Exception as e:
                last_model_msg = ""
                last_model_msg_2 = ""

            is_buy = False
            if model_info := strategy_handler.check_in_by_model(last_model_msg, last_model_msg_2):
                recommend_bid_price = model_info.get("recommend_bid_price")
                strategy_text += model_info["model_name"]
                is_buy = model_info.get("is_buy")

            # elif score_info := await self.get_buy_by_multi_factor_score(curr_price):
            #     for k, v in score_info.items():
            #         strategy_text += f"{k}:{v}分;"

            else:
                return

            recommend_price_data = self.get_recommend_price(curr_price)
            recommend_bid_price = recommend_bid_price or recommend_price_data["recommend_bid_price"]
            recommend_sl_price = recommend_price_data["sl_price"]
            recommend_tp_price = recommend_price_data["tp_price"]

            self.set_limit_price_url = f"{INNER_GET_SUBMIT_LIMIT_PRICE_URL}?" \
                                    f"symbol={self.symbol}" \
                                    f"&low_price={recommend_sl_price}" \
                                    f"&high_price={recommend_tp_price}&buy_price="

            if is_buy:
                redis_client = AllCache.get_client()
                redis_client.set(f"sl_tp:{self.symbol}", f"{recommend_sl_price}:{recommend_tp_price}")

            direction = f"<br> 🟢 短线买入信号: <b>{self.symbol.upper()}</b>" \
                        f"\n<br> 总分: {sum(score_info.values())}。" \
                        f"\n<br> 策略详情： {strategy_text}。" \
                        f"\n<br><br> 📈 建议买入价: {decimal2str(recommend_bid_price)}，" \
                        f"当前价: {decimal2str(curr_price)}。<br><br>"
            func_str = "get_buy_score_info"

            # TODO: 这里应该是实盘记录，回测记录需要单独出来，供策略回测优化。

            await TradeSignalHandler(self.symbol).add_bid_ticket(
                curr_price,
                recommend_bid_price,
                self.check_time,
                5,
                strategy_text,
                is_buy=is_buy
            )
            if not is_buy:
                return

        elif await self.has_limit_price_check((1,)):
            logger.debug(f"strategy sell check start, symbol:{self.symbol}")
            
            recommend_ask_price = None

            strategy_handler = StrategyHandle(
                self.kline_list_4h, self.kline_list_1h, self.kline_list_15m,
                self.bb_list_4h, self.bb_list_1h, self.bb_list_15m,
                self.macd_list_1d, self.macd_list_4h, self.macd_list_1h, self.macd_list_15m,
                self.kdj_list_1d, self.kdj_list_4h, self.kdj_list_1h, self.kdj_list_15m,
                self.rsi_list_4h, self.rsi_list_1h, self.rsi_list_15m
            )
            try:
                curr_order = await PlotBackTestTable.select().where(
                    PlotBackTestTable.symbol == self.symbol,
                ).order_by(PlotBackTestTable.id.desc()).limit(1).aio_get()
                curr_model_msg = curr_order.ask_plot_msg if curr_order.ask_plot_msg else curr_order.bid_plot_msg
            except PlotBackTestTable.DoesNotExist:
                curr_model_msg = ""

            is_sell = False
            need_notify = False
            part_direction = ""
            if model_info := strategy_handler.check_out_by_model(curr_model_msg):
                recommend_ask_price = model_info.get("recommend_ask_price")
                ask_plot_type = 5
                func_str = model_info["model_name"]
                part_direction = func_str
                is_sell = model_info.get("is_sell")
                if is_sell:
                    need_notify = True
                
            # elif part_direction_info := strategy_handler._get_sell_direction_active_taking_profit(curr_price):
            #     ask_plot_type = 6
            #     func_str = "_get_sell_direction_active_taking_profit"

            #     part_direction = part_direction_info.get("direction")
            #     recommend_ask_price = part_direction_info.get("recommend_ask_price")
            # elif part_direction := strategy_handler._get_sell_direction_stop_loss(curr_price):
            #     ask_plot_type = 7
            #     func_str = "_get_sell_direction_stop_loss"
            # elif part_direction := strategy_handler._get_exit_score():
            #     ask_plot_type = 8
            #     func_str = "_get_exit_score"
            else:
                redis_client = AllCache.get_client()
                cache_data = redis_client.get(f"sl_tp:{self.symbol}")
                if not cache_data:
                    return

                func_str = "tp_sl"
                limit_price = MarketPriceLimitCache.hget(self.symbol)
                if not limit_price:
                    return
                set_time, limit_low_price, limit_high_price = limit_price.split(":")

                sl_price, tp_price = map(Decimal, (limit_low_price, limit_high_price))

                if curr_price >= tp_price:
                    part_direction += "当前价格触及止盈价，止盈离场。"
                    recommend_ask_price = curr_price
                    ask_plot_type = 8
                    need_notify = True
                elif curr_price <= min(sl_price, self.bb_list_1h[0].bblower):
                    part_direction += "当前价格触及止损价，止损离场。"
                    recommend_ask_price = sl_price
                    ask_plot_type = 9
                    need_notify = True
                else:
                    return

            if not recommend_ask_price:
                depth_prices_data = self.get_depth_prices(curr_price)
                recommend_ask_price = depth_prices_data["recommend_ask_price"]

            direction = f"<br> 🔴 短线卖出信号: <b>{self.symbol.upper()}</b> " \
                        f"<br> {part_direction}" \
                        f"<br><br> 📉 建议卖出价：{decimal2str(recommend_ask_price)}，" \
                        f"当前价: {decimal2str(curr_price)}。" \

            if ask_plot_type in [5, 9]:
                await TradeSignalHandler(self.symbol).update_ask_ticket(
                    curr_price,
                    recommend_ask_price,
                    self.check_time,
                    ask_plot_type,
                    part_direction,
                    is_sell=is_sell
                )
            
            if not need_notify:
                return

        else:
            return

        email_msg_md5_str = f"plotGpt:{func_str}:{self.symbol}:{open_ts}"

        self.result[self.symbol] = template_strategy_notice(
            direction, open_ts, decimal2str(curr_price),
            self.check_time, self.close_monitor_url, self.set_limit_price_url)

        logger.info(
            f"StrategyCheckHandle.get_buy_score_info finish, start end_msg, symbol:{self.symbol}, ts:{self.check_time}")
        receiver_list = await self.get_receiver_list()
        await self.send_msg(self.email_title, email_msg_md5_str, receiver_list=receiver_list)

    async def get_receiver_list(self):
        query = await UserSymbolPlotTable.select(UserSymbolPlotTable.user_id).where(
            UserSymbolPlotTable.symbol == self.symbol).aio_execute()
        user_ids = [i.user_id for i in query]

        query = await UserInfoTable.select(UserInfoTable.email).where(UserInfoTable.uuid.in_(user_ids)).aio_execute()
        user_emails = [i.email for i in query]
        return user_emails

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
