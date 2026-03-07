#! /usr/bin/env python
# coding:utf8

import asyncio
import hashlib
import logging
import random
import time
from decimal import Decimal

import aiohttp

from business.market import MarketPriceHandler, SymbolHandle
from business.trade_signal_recorder import TradeSignalHandler
from cache import AllCache
from cache.plot import (CheckKdjCrossGateCache,
                        CheckMacdCrossGateCache, CheckMacdTrendGateCache)
from exts import async_database
from models.market import BnSymbolTable, EmaTable, KdjTable, KlineTable, MacdTable, RsiTable, BollTable
from models.user import EmailMsgHistoryTable, UserSymbolPlotTable
from models.order import PlotBackTestTable
from models.wallet import TotalBalanceHistoryTable
from msgqueue.queue import push_plot_mq
from settings.constants import (INNER_GET_DELETE_KDJ_CROSS_URL,
                                INNER_GET_DELETE_LIMIT_PRICE_URL,
                                INNER_GET_DELETE_MACD_CROSS_URL,
                                INNER_GET_DELETE_MACD_TREND_URL,
                                INNER_GET_DELETE_KDJ_CROSS_URL,
                                INNER_GET_PRICE_URL,
                                INNER_GET_UPDATE_PRICE_URL, PLOT_INTERVAL_CONFIG,
                                PLOT_INTERVAL_LIST)
from utils.common import check_lock_latest, decimal2str, str2decimal, ts2bjfmt
from utils.templates import (template_asset_notice, template_ema_cross_notice,
                             template_kdj_cross_notice, template_macd_cross_notice,
                             template_macd_trend_notice)

from msgqueue.tasks.base import BasePlotHandle, get_plot_symbols_info
from msgqueue.tasks.strategy import StrategyCheckHandle

logger = logging.getLogger(__name__)


async def check_price(*args, **kwargs):
    market_price_handler = MarketPriceHandler()

    for symbol, price in market_price_handler.get_all_limit_price().items():
        await PlotPriceHandle(symbol, price).check_limit_price()

    all_curr_prices = market_price_handler.get_current_price()
    await TradeSignalHandler().update_real_ticket(all_curr_prices)
    

async def check_break_history_top_price(*args, **kwargs):
    await TopPriceTaskHandle().check_break_history_top_price()


async def update_all_symbols(*args, **kwargs):
    await TopPriceTaskHandle().update_all_symbols()


async def cleanup_inactive_symbols(*args, **kwargs):
    await TopPriceTaskHandle().cleanup_inactive_symbols()
    SymbolHandle().refresh_symbol_cache()


async def check_balance(*args, **kwargs):
    await PlotAssetHandle().check_balance()


async def check_strategy(*args, **kwargs):
    logger.debug("check_strategy")

    redis_client = AllCache.get_client()

    symbols_info = await get_plot_symbols_info(redis_client)
    for symbol in symbols_info.keys():
        if symbol.lower() == "btcusdt":
            continue
        await push_plot_mq({
            "bp": "check_strategy_by_symbol",
            "symbol": symbol,
        })
    redis_client.close()


async def check_strategy_by_symbol(val):
    symbol = val.get("symbol")
    if not symbol:
        logger.error(f"check_strategy_by_symbol, {val}")
        return
    await StrategyCheckHandle(symbol).check()


async def break_4_hours_strategy(*args, **kwargs):
    await StrategyCheckHandle().break_4_hours_strategy()



async def check_kdj_cv(*args, **kwargs):
    pass


class PlotAssetHandle(BasePlotHandle):
    def __init__(self):
        super(PlotAssetHandle, self).__init__()
        self.user_id = 2
        self.exchange_platform = "binance"

    async def check_balance(self, limit_count=9):
        # TODO: 需要处理 当日净充值和净划入
        self.result["check_balance"] = []

        query = (
            TotalBalanceHistoryTable.select()
            .where(
                TotalBalanceHistoryTable.user_id == self.user_id,
                TotalBalanceHistoryTable.exchange_platform == self.exchange_platform,
            )
            .order_by(TotalBalanceHistoryTable.id.desc())
            .limit(limit_count)
        )
        query_data = [row for row in query][::-1]
        for i, row in enumerate(query_data):
            if i == 0:
                profit_amount, profit_ratio = "", ""
            else:
                profit_amount = row.usdt_val - Decimal(query_data[i - 1].usdt_val)
                profit_ratio = "{}%".format(
                    decimal2str(
                        (profit_amount / Decimal(query_data[i - 1].usdt_val)) * 100,
                        num=2,
                    )
                )
                profit_amount = (
                    f"+${decimal2str(profit_amount, num=2)}"
                    if profit_amount > 0
                    else f"-${decimal2str(profit_amount, num=2)[1:]}"
                )

            self.result["check_balance"].append(
                template_asset_notice(
                    decimal2str(row.btcusdt_price, num=2),
                    decimal2str(row.btc_val, num=2),
                    decimal2str(row.usdt_val, num=2),
                    row.create_ts,
                    profit_amount,
                    profit_ratio,
                )
            )

        email_msg_md5_str = f"check_balance:{query_data[-1].create_ts}"
        email_msg_md5 = hashlib.md5(email_msg_md5_str.encode("utf8")).hexdigest()
        try:
            return EmailMsgHistoryTable.get(
                EmailMsgHistoryTable.msg_md5 == email_msg_md5
            )
        except EmailMsgHistoryTable.DoesNotExist:
            pass

        email_content = "".join(self.result["check_balance"][::-1])
        EmailMsgHistoryTable.create(msg_md5=email_msg_md5, msg_content=email_content)
        email_title = f"check_balance"
        await self.send_msg(email_title, email_content)


class TopPriceTaskHandle(BasePlotHandle):
    def __init__(self):
        self.price_url = "https://api.binance.com/api/v3/ticker/price"
        self.kline_url = "https://api.binance.com/api/v3/klines"
        super().__init__()

    async def cleanup_inactive_symbols(self):
        """ 清除没有产生 有效交易信号 的symbol """
        target_ts = int(time.time()) - 40 * 3600
        has_in_symbol_list = []
        has_pending_symbol_list = []
        for row in await PlotBackTestTable.select().aio_execute():
            if row.bid_plot_msg and 'model_top_rise' in row.bid_plot_msg:
                has_in_symbol_list.append(row.symbol)
                continue

            if row.bid_ts <= target_ts:
                if row.bid_plot_msg and 'model_oscillation' in row.bid_plot_msg:
                    has_pending_symbol_list.append(row.symbol)
                elif row.ask_plot_msg and 'model_oscillation' in row.ask_plot_msg:
                    has_pending_symbol_list.append(row.symbol)

        need_update_del_symbol_list = []
        for symbol in has_pending_symbol_list:
            if symbol not in has_in_symbol_list:
                need_update_del_symbol_list.append(symbol)

        for i in await UserSymbolPlotTable.select().aio_execute():
            if i.create_ts > target_ts:
                continue
            if i.symbol not in has_in_symbol_list:
                need_update_del_symbol_list.append(i.symbol)
        need_update_del_symbol_list = list(set(need_update_del_symbol_list))

        # print(f"需要更新的交易对：{need_update_del_symbol_list}")
        logger.info(f"cleanup_inactive_symbols, need_update_del_symbol_list:{need_update_del_symbol_list}")
        for symbol in need_update_del_symbol_list:
            if symbol in ["btcusdt", "ethusdt", "solusdt", "dogeusdt", "xrpusdt"]:
                continue

            await PlotBackTestTable.delete().where(PlotBackTestTable.symbol == symbol).aio_execute()

            await UserSymbolPlotTable.delete().where(UserSymbolPlotTable.symbol == symbol).aio_execute()

            kline_del_rows = await KlineTable.delete().where(KlineTable.symbol == symbol).aio_execute()
            macd_del_rows = await MacdTable.delete().where(MacdTable.symbol == symbol).aio_execute()
            kdj_del_rows = await KdjTable.delete().where(KdjTable.symbol == symbol).aio_execute()
            rsi_del_rows = await RsiTable.delete().where(RsiTable.symbol == symbol).aio_execute()
            boll_del_rows = await BollTable.delete().where(BollTable.symbol == symbol).aio_execute()

    async def update_all_symbols(self):
        all_symbols_list = []
        async with aiohttp.ClientSession() as session:
            async with session.get(self.price_url) as response:
                data = await response.json()
                for item in data:
                    symbol = item["symbol"]
                    if symbol.endswith("USDT"):
                        all_symbols_list.append(symbol.lower())
                        
        old_symbols_list = [i.symbol for i in await BnSymbolTable.select().aio_execute()]

        count = 0
        async with async_database.aio_atomic(): 
            for symbol in list(set(all_symbols_list)):
                if symbol in old_symbols_list:
                    continue
                else:
                    await BnSymbolTable.aio_create(symbol=symbol, is_valid=True)
                    count += 1
                
        logger.info("update_all_symbols, count: %s", count)
        return all_symbols_list
                    
    async def check_break_history_top_price(self):
        bn_symbols_list = [i.symbol for i in 
                           await BnSymbolTable.select(BnSymbolTable.symbol).where(
                               BnSymbolTable.is_valid).aio_execute()]
        if not bn_symbols_list:
            bn_symbols_list = await self.update_all_symbols()

        user_symbols_list = [i.symbol for i in
                             await UserSymbolPlotTable.select(UserSymbolPlotTable.symbol).aio_execute()]
        for symbol in user_symbols_list:
            if symbol in bn_symbols_list:
                bn_symbols_list.remove(symbol)
                continue
            await self._check_break_history_top_price_from_db(symbol)
        
        for symbol in bn_symbols_list:
            await self._check_break_history_top_price_from_api(symbol)

    async def _check_break_history_top_price_from_api(self, symbol):
        await asyncio.sleep(random.uniform(0.1, 0.8))
        
        # 添加请求间隔控制
        if hasattr(self, '_last_request_time'):
            time_diff = time.time() - self._last_request_time
            if time_diff < 0.1:  # 最小间隔100ms
                await asyncio.sleep(0.1 - time_diff)
        
        self._last_request_time = time.time()
        
        try:
            async with aiohttp.ClientSession() as session:
                limit = 36
                async with session.get(
                        self.kline_url,
                        params={
                            "symbol": symbol.upper(), "interval": "1h", "limit": limit},
                        # timeout=10  # 设置10秒超时
                ) as response:
                    data = await response.json()
                    if len(data) < limit:
                        return
                    
                    high_price_list = [i[2] for i in data]
                    curr_high_price = high_price_list[-1]
                    history_high_price = max(high_price_list[:-1])
                    if curr_high_price <= history_high_price:
                        return
                    curr_ts = data[-1][0]
        except Exception as e:
            logger.error(f"_check_break_history_top_price_from_api: {e} - {symbol}")
            return

        symbol_handler = SymbolHandle(symbol=symbol, user_id="root")
        await symbol_handler.add_symbol()
        symbol_handler.refresh_symbol_cache()
                
        email_title = f"{symbol} Top Price Notice"
        
        self.result[symbol] = f"""
        <br><br><b> {symbol}: </b><br> 🚀 new high price:{curr_high_price},
        """ 

        email_msg_md5_str = f"check_break_history_top_price:{symbol}:{curr_ts}"
        await self.send_msg(email_title, email_msg_md5_str)
        del self.result[symbol]
        
    async def _check_break_history_top_price_from_db(self, symbol):
        query = KlineTable.select().where(
            KlineTable.symbol == symbol, KlineTable.interval_val == "1h"
        ).order_by(KlineTable.id.desc()).limit(20)
        query_list = [i for i in await query.aio_execute()]
        if len(query_list) < 20:
            return
        
        high_price_list = [i.high_price for i in query_list]
        
        curr_high_price = high_price_list[0]
        history_high_price = max(high_price_list[1:])
        if curr_high_price <= history_high_price:
            return
        
        symbol_handler = SymbolHandle(symbol=symbol, user_id="root")
        await symbol_handler.add_symbol()
        symbol_handler.refresh_symbol_cache()

        email_title = f"{symbol} Top Price Notice"
        
        self.result[symbol] = f"""
        <br><br><b> {symbol}: </b><br>🔥 🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀 new high price:{curr_high_price},
        """ 

        email_msg_md5_str = f"check_break_history_top_price:{symbol}:{query_list[0].open_ts}"
        await self.send_msg(email_title, email_msg_md5_str)
        del self.result[symbol]


class PlotPriceHandle(BasePlotHandle):
    def __init__(self, symbol, price):
        super().__init__()
        set_time, limit_low_price, limit_high_price = price

        self.symbol = symbol
        self.limit_low_price = limit_low_price
        self.limit_high_price = limit_high_price
        self.market_price_handler = MarketPriceHandler()
        self.init_plot_indicator()

    def init_plot_indicator(self):
        self.low_incr = "0.95"
        self.high_incr = "1.05"

    def __get_current_price(self):
        current_price = self.market_price_handler.get_current_price(self.symbol).get(self.symbol)
        if not current_price:
            self.result[
                self.symbol
            ] = f"""
            <br><br><b> {self.symbol}: </b><br>http get price fail.
            <br><a href={INNER_GET_PRICE_URL}{self.symbol}>Get current price info.</a>
            <br>now time: {ts2bjfmt()}.<a>
            <br><a href={INNER_GET_DELETE_LIMIT_PRICE_URL}{self.symbol}>Delete price check.<a>
            """
            return

        return current_price

    def __check_limit_low_price(self, current_price):
        if not self.limit_low_price:
            return
        if current_price > self.limit_low_price:
            return

        self.result[
            self.symbol
        ] = f"""
        <br><br><b> {self.symbol}: </b><br>‼️ new low price:{current_price},
        <br>last limit low price:{self.limit_low_price} !!!
        <br><a href={INNER_GET_PRICE_URL}{self.symbol}>Get current price info.</a>
        <br><a href={INNER_GET_UPDATE_PRICE_URL}{"low"}/{self.symbol}/>Update new low price.<a>
        <br>now time: {ts2bjfmt()}.<a>
        <br><a href={INNER_GET_DELETE_LIMIT_PRICE_URL}{self.symbol}>Delete price check.<a>
        """

        # TODO:脚本任务, 自动调整本地限价, 同时调用API调整server限价
        # self.market_price_handler.set_limit_price(
        #     self.symbol,
        #     Decimal(decimal2str(self.limit_low_price * Decimal(self.low_incr))),
        #     Decimal(decimal2str(self.limit_high_price * Decimal(self.low_incr))),
        # )

    def __check_limit_high_price(self, current_price):
        if not self.limit_high_price:
            return
        if current_price < self.limit_high_price:
            return

        self.result[
            self.symbol
        ] = f"""
        <br><br><b> {self.symbol}: </b><br>💰💰 new high price:{current_price},
        <br>last limit high price:{self.limit_high_price} !!!
        <br><a href={INNER_GET_PRICE_URL}{self.symbol}>Get current price info.</a>
        <br><a href={INNER_GET_UPDATE_PRICE_URL}{"high"}/{self.symbol}/>Update new high price.<a>
        <br>now time: {ts2bjfmt()}.<a>
        <br><a href={INNER_GET_DELETE_LIMIT_PRICE_URL}{self.symbol}>Delete price check.<a>
        """

        # TODO:脚本任务, 自动调整本地限价, 同时调用API调整server限价
        # self.market_price_handler.set_limit_price(
        #     self.symbol,
        #     Decimal(decimal2str(self.limit_low_price * Decimal(self.high_incr))),
        #     Decimal(decimal2str(self.limit_high_price * Decimal(self.high_incr))),
        # )
        
    async def check_limit_price(self):
        email_title = f"{self.symbol} Price Notice"

        current_price = self.__get_current_price()
        if not current_price:
            return await self.send_msg(email_title, "")

        self.__check_limit_low_price(current_price)
        self.__check_limit_high_price(current_price)
        
        email_msg_md5_str = f"check_limit_price:{self.symbol}:{self.limit_low_price}:{self.limit_high_price}"
        await self.send_msg(email_title, email_msg_md5_str)
