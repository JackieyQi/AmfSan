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
        from business.monitor import enqueue_monitor_notice
        monitors = list(await UserSymbolPlotTable.select().where(
            UserSymbolPlotTable.symbol == self.symbol,
            UserSymbolPlotTable.is_valid == True,
        ).aio_execute())
        if not monitors:
            return
        await self.initialize_indicators()
        # Only the current 1h/4h/1d path is used. New/incomplete or stale data must not alert.
        for interval, candles, macd, kdj, rsi, boll in (
            ("1h", self.kline_list_1h, self.macd_list_1h, self.kdj_list_1h, self.rsi_list_1h, self.bb_list_1h),
            ("4h", self.kline_list_4h, self.macd_list_4h, self.kdj_list_4h, self.rsi_list_4h, self.bb_list_4h),
        ):
            if any(len(values) < 10 for values in (candles, macd, kdj, rsi, boll)):
                logger.info("monitor waiting for indicators, symbol:%s, interval:%s", self.symbol, interval)
                return
            expected_ts = self.check_time // PLOT_INTERVAL_CONFIG[interval]["interval_sec"] * PLOT_INTERVAL_CONFIG[interval]["interval_sec"]
            if any(ts < expected_ts for ts in (candles[0].open_ts, macd[0].opening_ts,
                    kdj[0].open_ts, rsi[0].open_ts, boll[0].open_ts)):
                logger.info("monitor waiting for current candle, symbol:%s, interval:%s", self.symbol, interval)
                return
        if not self.macd_list_1d or self.macd_list_1d[0].opening_ts < self.check_time // 86400 * 86400:
            return
        handler = StrategyHandle(
            self.kline_list_4h, self.kline_list_1h, self.kline_list_15m,
            self.bb_list_4h, self.bb_list_1h, self.bb_list_15m,
            self.macd_list_1d, self.macd_list_4h, self.macd_list_1h, self.macd_list_15m,
            self.kdj_list_1d, self.kdj_list_4h, self.kdj_list_1h, self.kdj_list_15m,
            self.rsi_list_4h, self.rsi_list_1h, self.rsi_list_15m,
        )
        signals = {}
        for row in monitors:
            if row.monitor_direction not in signals:
                signals[row.monitor_direction] = handler.check_monitor_direction(row.monitor_direction)
            if signals[row.monitor_direction]:
                await enqueue_monitor_notice(row, signals[row.monitor_direction],
                                             self.kline_list_1h[0].close_price,
                                             self.kline_list_1h[0].open_ts)
