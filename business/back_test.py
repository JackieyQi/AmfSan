#! /usr/bin/env python
# -*- coding: UTF-8 -*-

import time
from decimal import Decimal
from exts import async_database
from models.order import PlotBackTestTable
from cache.order import MarketPriceLimitCache
from utils.common import str2decimal, decimal2decimal, decimal2str, convert_seconds
from utils.exception import StandardResponseExc
from cache import AllCache
from .market import MarketPriceHandler


class BackTestViewHandler(object):
    async def get_detail_record(self, symbol, record_id):
        try:
            record = await PlotBackTestTable.select().where(PlotBackTestTable.id == record_id).aio_get()
        except PlotBackTestTable.DoesNotExist:
            raise StandardResponseExc(msg="Record not exists.")

        result = {
                "id": record.id,
                "symbol": record.symbol,
                "bid_curr_price": decimal2str(record.bid_curr_price),
                "bid_price": decimal2str(record.bid_price),
                "bid_ts": record.bid_ts,
                "bid_plot_type": record.bid_plot_type,
                "bid_plot_msg": record.bid_plot_msg,
                "buy_price": decimal2str(record.buy_price),
                "buy_ts": record.buy_ts,
                "ask_curr_price": decimal2str(record.ask_curr_price),
                "ask_price": decimal2str(record.ask_price),
                "ask_ts": record.ask_ts,
                "ask_plot_type": record.ask_plot_type,
                "ask_plot_msg": record.ask_plot_msg,
                "sell_price": decimal2str(record.sell_price),
                "sell_ts": record.sell_ts,
                "hold_time": self._format_hold_time(record.hold_time),
                "profit_percent": f"{record.profit_percent}%",
                # "profit_amount": profit_amount,
                "status": record.status,
                "status_text": self._get_status_text(record.status)
            }
        return result

    async def get_back_test_records(self, page=1, page_size=10, symbol=None, status=None):
        """
        分页查询回测记录

        Args:
            page (int): 当前页码，默认为1
            page_size (int): 每页记录数，默认为10
            symbol (str, optional): 筛选的交易对
            status (int, optional): 筛选的状态

        Returns:
            dict: 包含分页数据和总记录数的JSON响应
        """
        # 构建基础查询
        query = PlotBackTestTable.select(
            PlotBackTestTable.id, PlotBackTestTable.symbol, PlotBackTestTable.buy_price, PlotBackTestTable.buy_ts,
            PlotBackTestTable.sell_price, PlotBackTestTable.sell_ts, PlotBackTestTable.hold_time,
            PlotBackTestTable.profit_percent, PlotBackTestTable.status
        )

        # 添加筛选条件
        if symbol:
            query = query.where(PlotBackTestTable.symbol == symbol)
        if status is not None:  # 0是有效值，所以用is not None判断
            query = query.where(PlotBackTestTable.status == status)

        # 获取总记录数
        total_count = await query.aio_count()

        # 计算总页数
        total_pages = (total_count + page_size - 1) // page_size

        # 添加分页
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        # 添加排序 (默认按id降序排列，最新记录优先)
        query = query.order_by(PlotBackTestTable.id.desc())

        # 执行查询
        records = await query.aio_execute()

        # 转换结果为字典列表
        result_list = []
        for record in records:
            # 计算利润金额（如果有买入和卖出价格）
            # profit_amount = 0
            # if record.buy_price > 0 and record.sell_price > 0:
            #     profit_amount = float(record.sell_price) - float(record.buy_price)

            result_list.append({
                "id": record.id,
                "symbol": record.symbol,
                # "bid_curr_price": decimal2str(record.bid_curr_price),
                # "bid_price": decimal2str(record.bid_price),
                # "bid_ts": record.bid_ts,
                # "bid_plot_type": record.bid_plot_type,
                # "bid_plot_msg": record.bid_plot_msg,
                "buy_price": decimal2str(record.buy_price),
                "buy_ts": record.buy_ts,
                # "ask_curr_price": decimal2str(record.ask_curr_price),
                # "ask_price": decimal2str(record.ask_price),
                # "ask_ts": record.ask_ts,
                # "ask_plot_type": record.ask_plot_type,
                # "ask_plot_msg": record.ask_plot_msg,
                "sell_price": decimal2str(record.sell_price),
                "sell_ts": record.sell_ts,
                "hold_time": self._format_hold_time(record.hold_time),
                "profit_percent": f"{record.profit_percent}%",
                # "profit_amount": profit_amount,
                "status": record.status,
                "status_text": self._get_status_text(record.status)
            })

        # 构建响应数据
        response_data = {
                "records": result_list,
                "pagination": {
                    "current_page": page,
                    "page_size": page_size,
                    "total_count": total_count,
                    "total_pages": total_pages
                }
            }
        return response_data

    def _get_status_text(self, status):
        """获取状态文本描述"""
        status_map = {
            0: "挂买单中",
            1: "买入成功，等待卖出",
            2: "买入失败",
            3: "挂卖单中",
            4: "卖出成功",
            5: "挂卖单失败，以市价卖出"
        }
        return status_map.get(status, "未知状态")

    def _format_hold_time(self, hold_time):
        days, hours, minutes = convert_seconds(hold_time)
        format_hold_time = ""
        if days:
            format_hold_time += f"{days}天"
        if hours:
            format_hold_time += f"{hours}小时"
        if minutes:
            format_hold_time += f"{minutes}分钟"
        return format_hold_time


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
                ).order_by(PlotBackTestTable.bid_ts.desc()).aio_get()

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
                        redis_client = AllCache.get_client()
                        cache_data = redis_client.get(f"sl_tp:{self.symbol}")
                        if not cache_data:
                            sl_price = curr_price * Decimal("0.95")
                            tp_price = curr_price * Decimal("1.05")
                        else:
                            _d = cache_data.split(":")
                            sl_price = Decimal(_d[0])
                            tp_price = Decimal(_d[1])

                        market_price_handler.set_limit_price(
                            _d.symbol, sl_price, tp_price, curr_ts)

                    elif _d.bid_ts < (curr_ts - 5400):
                        _d.buy_ts = curr_ts
                        _d.status = 2
                        await _d.aio_save()

                elif _d.status == 3:
                    if curr_price >= _d.ask_price:
                        _d.sell_price = _d.ask_price
                        _d.sell_ts = curr_ts
                        _d.hold_time = curr_ts - _d.buy_ts
                        _d.profit_percent = decimal2decimal(((_d.ask_price - _d.buy_price) / _d.buy_price)*Decimal("100"), 1)
                        _d.status = 4
                        await _d.aio_save()

                        self.set_last_trade_time(curr_ts)

                    # TODO: 挂卖单->延迟挂单时间
                    elif _d.ask_ts < (curr_ts - 7200):
                        _d.sell_price = curr_price
                        _d.sell_ts = curr_ts
                        _d.hold_time = curr_ts - _d.buy_ts
                        _d.profit_percent = decimal2decimal(((curr_price - _d.buy_price) / _d.buy_price)*Decimal("100"), 1)
                        _d.status = 5
                        await _d.aio_save()

                        self.set_last_trade_time(curr_ts)


