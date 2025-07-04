#! /usr/bin/env python
# coding:utf8

from utils.authentication import HTTPMethodView, ProtectedView
from business.trade_signal_recorder import TradeSignalViewHandler
from business.strategy import StrategyHandle
from utils.exception import StandardResponseExc
from models.market import KlineTable, MacdTable, KdjTable, RsiTable, BollTable


class TradeSignalRecordsView(ProtectedView):
    need_auth = {"get": True, }

    async def get(self, request):
        user = request.ctx.user

        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 10))
        symbol = request.args.get("symbol")
        status = request.args.get("status")
        if status is not None:
            status = int(status)
        return await TradeSignalViewHandler(user.user_id).get_trade_records(page, page_size, symbol, status)


class TradeSignalRecordDetailView(ProtectedView):
    need_auth = {"get": True, }

    async def get(self, request):
        user = request.ctx.user

        symbol = request.args.get("symbol")
        record_id = request.args.get("id")
        if not all([symbol, record_id]):
            raise StandardResponseExc(msg="Missing required fields")

        return await TradeSignalViewHandler(user.user_id).get_detail_record(symbol, record_id)


class SymbolScoreView(HTTPMethodView):
    async def get(self, request):
        """
        获取symbol的进出场分数
        参数:
            symbol: 交易对符号 (必填)
        
        返回:
            {
                "symbol": "btcusdt",
                "entry_score": 0.75,    # 进场分数 (0-1)
                "exit_score": 0.25,     # 出场分数 (0-1)
                "recommendation": "buy|sell|hold",
                "timestamp": 1234567890
            }
        """
        symbol = request.args.get("symbol")
        
        if not symbol:
            raise StandardResponseExc(msg="Missing required field: symbol")
        return await self._calculate_symbol_score(symbol.strip().lower())
    
    async def _calculate_symbol_score(self, symbol: str) -> dict:
        """
        计算symbol的进出场分数
        
        Args:
            symbol: 交易对符号
            
        Returns:
            包含进出场分数的字典
        """
        # 获取K线数据
        kline_4h = await KlineTable.select().where(
            KlineTable.symbol == symbol,
            KlineTable.interval_val == "4h"
        ).order_by(KlineTable.id.desc()).limit(30).aio_execute()
        
        kline_1h = await KlineTable.select().where(
            KlineTable.symbol == symbol,
            KlineTable.interval_val == "1h"
        ).order_by(KlineTable.id.desc()).limit(30).aio_execute()
        
        kline_15m = await KlineTable.select().where(
            KlineTable.symbol == symbol,
            KlineTable.interval_val == "15m"
        ).order_by(KlineTable.id.desc()).limit(30).aio_execute()
        
        # 获取MACD数据
        macd_1d = await MacdTable.select().where(
            MacdTable.symbol == symbol,
            MacdTable.interval_val == "1d"
        ).order_by(MacdTable.id.desc()).limit(30).aio_execute()
        
        macd_4h = await MacdTable.select().where(
            MacdTable.symbol == symbol,
            MacdTable.interval_val == "4h"
        ).order_by(MacdTable.id.desc()).limit(30).aio_execute()
        
        macd_1h = await MacdTable.select().where(
            MacdTable.symbol == symbol,
            MacdTable.interval_val == "1h"
        ).order_by(MacdTable.id.desc()).limit(30).aio_execute()
        
        macd_15m = await MacdTable.select().where(
            MacdTable.symbol == symbol,
            MacdTable.interval_val == "15m"
        ).order_by(MacdTable.id.desc()).limit(30).aio_execute()
        
        # 获取KDJ数据
        kdj_1d = await KdjTable.select().where(
            KdjTable.symbol == symbol,
            KdjTable.interval_val == "1d"
        ).order_by(KdjTable.id.desc()).limit(2).aio_execute()
        
        kdj_4h = await KdjTable.select().where(
            KdjTable.symbol == symbol,
            KdjTable.interval_val == "4h"
        ).order_by(KdjTable.id.desc()).limit(30).aio_execute()
        
        kdj_1h = await KdjTable.select().where(
            KdjTable.symbol == symbol,
            KdjTable.interval_val == "1h"
        ).order_by(KdjTable.id.desc()).limit(30).aio_execute()
        
        kdj_15m = await KdjTable.select().where(
            KdjTable.symbol == symbol,
            KdjTable.interval_val == "15m"
        ).order_by(KdjTable.id.desc()).limit(30).aio_execute()
        
        # 获取RSI数据
        rsi_4h = await RsiTable.select().where(
            RsiTable.symbol == symbol,
            RsiTable.interval_val == "4h"
        ).order_by(RsiTable.id.desc()).limit(30).aio_execute()
        
        rsi_1h = await RsiTable.select().where(
            RsiTable.symbol == symbol,
            RsiTable.interval_val == "1h"
        ).order_by(RsiTable.id.desc()).limit(30).aio_execute()
        
        rsi_15m = await RsiTable.select().where(
            RsiTable.symbol == symbol,
            RsiTable.interval_val == "15m"
        ).order_by(RsiTable.id.desc()).limit(30).aio_execute()
        
        # 获取布林带数据
        bb_4h = await BollTable.select().where(
            BollTable.symbol == symbol,
            BollTable.interval_val == "4h"
        ).order_by(BollTable.id.desc()).limit(30).aio_execute()
        
        bb_1h = await BollTable.select().where(
            BollTable.symbol == symbol,
            BollTable.interval_val == "1h"
        ).order_by(BollTable.id.desc()).limit(30).aio_execute()
        
        bb_15m = await BollTable.select().where(
            BollTable.symbol == symbol,
            BollTable.interval_val == "15m"
        ).order_by(BollTable.id.desc()).limit(30).aio_execute()
            
        if not all([kline_4h, kline_1h, kline_15m, bb_4h, bb_1h, bb_15m, macd_1d, macd_4h, macd_1h, macd_15m, kdj_1d, kdj_4h, kdj_1h, kdj_15m, rsi_4h, rsi_1h, rsi_15m]):
            return "No data found."

        strategy_handle = StrategyHandle(
            kline_list_4h=list(kline_4h), 
            kline_list_1h=list(kline_1h), 
            kline_list_15m=list(kline_15m),
            bb_list_4h=list(bb_4h), 
            bb_list_1h=list(bb_1h), 
            bb_list_15m=list(bb_15m),
            macd_list_1d=list(macd_1d), 
            macd_list_4h=list(macd_4h), 
            macd_list_1h=list(macd_1h), 
            macd_list_15m=list(macd_15m),
            kdj_list_1d=list(kdj_1d), 
            kdj_list_4h=list(kdj_4h), 
            kdj_list_1h=list(kdj_1h), 
            kdj_list_15m=list(kdj_15m),
            rsi_list_4h=list(rsi_4h), 
            rsi_list_1h=list(rsi_1h), 
            rsi_list_15m=list(rsi_15m)
        )
        return strategy_handle.get_symbol_score(symbol)
