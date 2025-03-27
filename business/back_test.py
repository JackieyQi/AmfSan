#! /usr/bin/env python
# -*- coding: UTF-8 -*-

import time
from decimal import Decimal
from exts import async_database
from models.order import PlotBackTestTable
from cache.order import MarketPriceLimitCache
from utils.common import str2decimal
from cache import AllCache
from .market import MarketPriceHandler


class BackTestHandler(object):
    def __init__(self, symbol=None):
        self.symbol = symbol

    def set_last_trade_time(self, ts):
        redis_client = AllCache.get_client()
        key = "lastTradeTs"
        redis_client.set(key, ts)

    async def add_bid_ticket(self, curr_price, bid_price, bid_ts, bid_plot_type, bid_plot_msg):
        async with async_database.aio_atomic():
            await PlotBackTestTable.aio_create(
                symbol=self.symbol,
                bid_curr_price=curr_price,
                bid_price=bid_price,
                bid_ts=bid_ts,
                bid_plot_type=bid_plot_type,
                bid_plot_msg=bid_plot_msg,
            )

            # MarketPriceLimitCache.hset(
            #     self.symbol,
            #     "{}:{}:{}".format(
            #         bid_ts, curr_price * Decimal("0.95"), curr_price * Decimal("1.05")
            #     ),
            # )

    async def update_ask_ticket(self, curr_price, ask_price, ask_ts, ask_plot_type, ask_plot_msg):
        async with async_database.aio_atomic():
            try:
                last_ticket = await PlotBackTestTable.select().where(
                    PlotBackTestTable.symbol == self.symbol,
                    # PlotBackTestTable.buy_ts > 0,
                    # PlotBackTestTable.ask_ts == 0,
                ).order_by(PlotBackTestTable.id.desc()).aio_get()

                last_ticket.ask_curr_price = curr_price
                last_ticket.ask_price = ask_price
                last_ticket.ask_ts = ask_ts
                last_ticket.ask_plot_type = ask_plot_type
                last_ticket.ask_plot_msg = ask_plot_msg
                last_ticket.status = 3
                await last_ticket.aio_save()

                MarketPriceLimitCache.hdel(self.symbol)
            except PlotBackTestTable.DoesNotExist:
                pass

    async def update_real_ticket(self, all_curr_prices):
        curr_ts = int(time.time())
        market_price_handler = MarketPriceHandler()

        async with async_database.aio_atomic():
            db_data = await PlotBackTestTable.select().where(PlotBackTestTable.status.in_([0, 3])).aio_execute()

            for _d in db_data:
                # TODO: 优化实时价格获取->需要单独起 循环任务，根据k线价格范围，但是又没有1分钟k线
                curr_price = market_price_handler.get_current_price(_d.symbol).get("price")

                if not curr_price:
                    continue
                curr_price = str2decimal(curr_price)

                if _d.status == 0:
                    if curr_price <= _d.bid_price:
                        _d.buy_price = _d.bid_price
                        _d.buy_ts = curr_ts
                        _d.status = 1
                        await _d.aio_save()

                        # MarketPriceLimitCache.hset(
                        #     self.symbol,
                        #     "{}:{}:{}".format(
                        #         curr_ts, curr_price * Decimal("0.95"), curr_price * Decimal("1.05")
                        #     ),
                        # )
                        market_price_handler.set_limit_price(
                            _d.symbol, curr_price * Decimal("0.95"), curr_price * Decimal("1.05"), curr_ts)

                    elif _d.bid_ts < (curr_ts - 5400):
                        _d.buy_ts = curr_ts
                        _d.status = 2
                        await _d.aio_save()

                elif _d.status == 3:
                    if curr_price >= _d.ask_price:
                        _d.sell_price = _d.ask_price
                        _d.sell_ts = curr_ts
                        _d.hold_time = curr_ts - _d.buy_ts
                        _d.profit_percent = str2decimal(((_d.ask_price - _d.buy_price) / _d.buy_price)*Decimal("100"), 1)
                        _d.status = 4
                        await _d.aio_save()

                        self.set_last_trade_time(curr_ts)

                    # TODO: 挂卖单->延迟挂单时间
                    elif _d.ask_ts < (curr_ts - 7200):
                        _d.sell_price = curr_price
                        _d.sell_ts = curr_ts
                        _d.hold_time = curr_ts - _d.buy_ts
                        _d.profit_percent = str2decimal(((curr_price - _d.buy_price) / _d.buy_price)*Decimal("100"), 1)
                        _d.status = 5
                        await _d.aio_save()

                        self.set_last_trade_time(curr_ts)


