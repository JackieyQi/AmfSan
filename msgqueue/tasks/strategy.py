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
from models.user import UserSymbolPlotTable, UserInfoTable
from settings.constants import PLOT_INTERVAL_CONFIG, INNER_GET_DELETE_LIMIT_PRICE_URL, INNER_GET_SUBMIT_LIMIT_PRICE_URL
from utils.common import ts2bjfmt, decimal2decimal, decimal2str
from utils.hrequest import http_get_request
from utils.indicators import get_atr_price
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

        self.kline_list_4h = None
        self.kline_list_1h = None
        self.kline_list_15m = None
        
        self.macd_list_1d = None
        self.macd_list_4h = None
        self.macd_list_1h = None
        self.macd_list_15m = None
        
        self.kdj_list_1d = None
        self.kdj_list_4h = None
        self.kdj_list_1h = None
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
            self.kline_list_4h = list(_kline_list_4h)

            _query = self.get_kline_query("1h", limit_count=30)
            _kline_list_1h = await _query.aio_execute()
            self.kline_list_1h = list(_kline_list_1h)

            _query = self.get_kline_query("15m", limit_count=30)
            _kline_list_15m = await _query.aio_execute()
            self.kline_list_15m = list(_kline_list_15m)

            _query = self.get_macd_query("1d", limit_count=30)
            _macd_list_1d = await _query.aio_execute()
            self.macd_list_1d = list(_macd_list_1d)

            _query = self.get_macd_query("4h", limit_count=30)
            _macd_list_4h = await _query.aio_execute()
            self.macd_list_4h = list(_macd_list_4h)

            _query = self.get_macd_query("1h", limit_count=30)
            _macd_list_1h = await _query.aio_execute()
            self.macd_list_1h = list(_macd_list_1h)

            _query = self.get_macd_query("15m", limit_count=30)
            _macd_list_15m = await _query.aio_execute()
            self.macd_list_15m = list(_macd_list_15m)

            _query = self.get_kdj_query("1d", limit_count=2)
            _kdj_list_1d = await _query.aio_execute()
            self.kdj_list_1d = list(_kdj_list_1d)

            _query = self.get_kdj_query("4h", limit_count=30)
            _kdj_list_4h = await _query.aio_execute()
            self.kdj_list_4h = list(_kdj_list_4h)

            _query = self.get_kdj_query("1h", limit_count=30)
            _kdj_list_1h = await _query.aio_execute()
            self.kdj_list_1h = list(_kdj_list_1h)

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

            # This records signal tracking for review; it does not place exchange orders.

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
