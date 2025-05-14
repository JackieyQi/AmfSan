#! /usr/bin/env python
# coding:utf8

import backtrader as bt
from typing import Dict, Optional
from decimal import Decimal


class BacktestStrategy(bt.Strategy):
    """
    基于StrategyCheckHandle的回测策略
    使用多个技术指标组合来生成交易信号
    """
    
    params = (
        ('symbol', None),         # 交易对
        ('stop_loss', 0.05),      # 止损比例
        ('take_profit', 0.1),     # 止盈比例
        ('rsi_period', 14),       # RSI周期
        ('rsi_overbought', 70),   # RSI超买阈值
        ('rsi_oversold', 30),     # RSI超卖阈值
        ('macd_fast', 12),        # MACD快线周期
        ('macd_slow', 26),        # MACD慢线周期
        ('macd_signal', 9),       # MACD信号线周期
        ('boll_period', 20),      # 布林带周期
        ('boll_std', 2),          # 布林带标准差倍数
    )
        
    def __init__(self):
        self.order = None
        self.buy_price = None
        self.buy_time = None
        
        # 添加交易分析器
        self.analyzers.trades = bt.analyzers.TradeAnalyzer()
        
        # 打印策略参数
        self.log(f'****** 策略初始化: symbol={self.p.symbol} ******')
        
    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
            
        if order.status in [order.Completed]:
            if order.isbuy():
                self.buy_price = order.executed.price
                self.buy_time = self.data.datetime.datetime()
                self.log(f'买入执行: symbol={self.p.symbol}, 价格={order.executed.price:.8f}, 成本={order.executed.value:.8f}, 手续费={order.executed.comm:.8f}')
            else:
                self.log(f'卖出执行: symbol={self.p.symbol}, 价格={order.executed.price:.8f}, 成本={order.executed.value:.8f}, 手续费={order.executed.comm:.8f}')
                
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f'订单取消/保证金不足/拒绝: symbol={self.p.symbol}')
            
        self.order = None
        
    def notify_trade(self, trade):
        if not trade.isclosed:
            return
            
        pnl_perc = trade.pnl / trade.price * 100
        self.log(f'交易利润: symbol={self.p.symbol}, 毛利润={trade.pnl:.8f}, 净利润={trade.pnlcomm:.8f}, 盈亏比例={pnl_perc:.2f}%')
        
    def log(self, txt, dt=None):
        dt = dt or self.data.datetime.datetime()
        print(f'{dt.isoformat()}, {txt}')
        
    def next(self):
        # 如果有未完成的订单，不执行新的交易
        if self.order:
            return
        
        # 如果没有持仓
        if not self.position:
            # 检查是否满足买入条件
            if model_info := self._check_buy_signal():
                self.log(f"检测到买入信号: symbol={self.p.symbol}, model={model_info.get('model_name')}, "
                         f"open_price={self.data.open[0]}, close_price={self.data.close[0]}")
                self.order = self.buy()
                
        # 如果有持仓
        else:
            # 检查是否满足卖出条件
            if part_direction := self._check_sell_signal():
                self.log(f"检测到卖出信号: symbol={self.p.symbol}, direction={part_direction}, "
                         f"open_price={self.data.open[0]}, close_price={self.data.close[0]}")
                self.order = self.sell()
                
    def _check_buy_signal(self):
        """
        检查是否满足买入条件
        使用多个技术指标组合来生成买入信号
        """

        from business.strategy import StrategyHandle
        from models.market import KlineTable, BollTable, MacdTable, KdjTable, RsiTable

        curr_1h_open_ts = int(self.data.datetime.datetime().timestamp())

        kline_list_4h = KlineTable.select().where(KlineTable.symbol == self.p.symbol, KlineTable.interval_val == "4h", KlineTable.open_ts <= curr_1h_open_ts).order_by(KlineTable.open_ts.desc()).limit(30)
        kline_list_1h = KlineTable.select().where(KlineTable.symbol == self.p.symbol, KlineTable.interval_val == "1h", KlineTable.open_ts <= curr_1h_open_ts).order_by(KlineTable.open_ts.desc()).limit(30)

        bb_list_4h = BollTable.select().where(BollTable.symbol == self.p.symbol, BollTable.interval_val == "4h", BollTable.open_ts < curr_1h_open_ts).order_by(BollTable.open_ts.desc()).limit(30)
        bb_list_1h = BollTable.select().where(BollTable.symbol == self.p.symbol, BollTable.interval_val == "1h", BollTable.open_ts <= curr_1h_open_ts).order_by(BollTable.open_ts.desc()).limit(30)

        macd_list_1d = MacdTable.select().where(MacdTable.symbol == self.p.symbol, MacdTable.interval_val == "1d", MacdTable.opening_ts <= curr_1h_open_ts).order_by(MacdTable.opening_ts.desc()).limit(30)
        macd_list_4h = MacdTable.select().where(MacdTable.symbol == self.p.symbol, MacdTable.interval_val == "4h", MacdTable.opening_ts <= curr_1h_open_ts).order_by(MacdTable.opening_ts.desc()).limit(30)
        macd_list_1h = MacdTable.select().where(MacdTable.symbol == self.p.symbol, MacdTable.interval_val == "1h", MacdTable.opening_ts <= curr_1h_open_ts).order_by(MacdTable.opening_ts.desc()).limit(30)
        
        kdj_list_1d = KdjTable.select().where(KdjTable.symbol == self.p.symbol, KdjTable.interval_val == "1d", KdjTable.open_ts <= curr_1h_open_ts).order_by(KdjTable.open_ts.desc()).limit(30)
        kdj_list_4h = KdjTable.select().where(KdjTable.symbol == self.p.symbol, KdjTable.interval_val == "4h", KdjTable.open_ts <= curr_1h_open_ts).order_by(KdjTable.open_ts.desc()).limit(30)
        kdj_list_1h = KdjTable.select().where(KdjTable.symbol == self.p.symbol, KdjTable.interval_val == "1h", KdjTable.open_ts <= curr_1h_open_ts).order_by(KdjTable.open_ts.desc()).limit(30)
        
        rsi_list_4h = RsiTable.select().where(RsiTable.symbol == self.p.symbol, RsiTable.interval_val == "4h", RsiTable.open_ts <= curr_1h_open_ts).order_by(RsiTable.open_ts.desc()).limit(30)
        rsi_list_1h = RsiTable.select().where(RsiTable.symbol == self.p.symbol, RsiTable.interval_val == "1h", RsiTable.open_ts <= curr_1h_open_ts).order_by(RsiTable.open_ts.desc()).limit(30)

        handler = StrategyHandle(
            kline_list_4h, kline_list_1h,
            bb_list_4h, bb_list_1h,
            macd_list_1d, macd_list_4h, macd_list_1h,
            kdj_list_1d, kdj_list_4h, kdj_list_1h,
            rsi_list_4h, rsi_list_1h)
        
        return handler.get_buy_by_model_detect(self.data.close[0])
        
    def _check_sell_signal(self) -> bool:
        """
        检查是否满足卖出条件
        使用多个技术指标组合来生成卖出信号
        """
        from business.strategy import StrategyHandle
        from models.market import KlineTable, BollTable, MacdTable, KdjTable, RsiTable

        curr_1h_open_ts = int(self.data.datetime.datetime().timestamp())
        kline_list_4h = KlineTable.select().where(KlineTable.symbol == self.p.symbol, KlineTable.interval_val == "4h", KlineTable.open_ts <= curr_1h_open_ts).order_by(KlineTable.open_ts.desc()).limit(30)
        kline_list_1h = KlineTable.select().where(KlineTable.symbol == self.p.symbol, KlineTable.interval_val == "1h", KlineTable.open_ts <= curr_1h_open_ts).order_by(KlineTable.open_ts.desc()).limit(30)

        bb_list_4h = BollTable.select().where(BollTable.symbol == self.p.symbol, BollTable.interval_val == "4h", BollTable.open_ts <= curr_1h_open_ts).order_by(BollTable.open_ts.desc()).limit(30)
        bb_list_1h = BollTable.select().where(BollTable.symbol == self.p.symbol, BollTable.interval_val == "1h", BollTable.open_ts <= curr_1h_open_ts).order_by(BollTable.open_ts.desc()).limit(30)

        macd_list_1d = MacdTable.select().where(MacdTable.symbol == self.p.symbol, MacdTable.interval_val == "1d", MacdTable.opening_ts <= curr_1h_open_ts).order_by(MacdTable.opening_ts.desc()).limit(30)
        macd_list_4h = MacdTable.select().where(MacdTable.symbol == self.p.symbol, MacdTable.interval_val == "4h", MacdTable.opening_ts <= curr_1h_open_ts).order_by(MacdTable.opening_ts.desc()).limit(30)
        macd_list_1h = MacdTable.select().where(MacdTable.symbol == self.p.symbol, MacdTable.interval_val == "1h", MacdTable.opening_ts <= curr_1h_open_ts).order_by(MacdTable.opening_ts.desc()).limit(30)
        
        kdj_list_1d = KdjTable.select().where(KdjTable.symbol == self.p.symbol, KdjTable.interval_val == "1d", KdjTable.open_ts <= curr_1h_open_ts).order_by(KdjTable.open_ts.desc()).limit(30)
        kdj_list_4h = KdjTable.select().where(KdjTable.symbol == self.p.symbol, KdjTable.interval_val == "4h", KdjTable.open_ts <= curr_1h_open_ts).order_by(KdjTable.open_ts.desc()).limit(30)
        kdj_list_1h = KdjTable.select().where(KdjTable.symbol == self.p.symbol, KdjTable.interval_val == "1h", KdjTable.open_ts <= curr_1h_open_ts).order_by(KdjTable.open_ts.desc()).limit(30)
        
        rsi_list_4h = RsiTable.select().where(RsiTable.symbol == self.p.symbol, RsiTable.interval_val == "4h", RsiTable.open_ts <= curr_1h_open_ts).order_by(RsiTable.open_ts.desc()).limit(30)
        rsi_list_1h = RsiTable.select().where(RsiTable.symbol == self.p.symbol, RsiTable.interval_val == "1h", RsiTable.open_ts <= curr_1h_open_ts).order_by(RsiTable.open_ts.desc()).limit(30)

        handler = StrategyHandle(
            kline_list_4h, kline_list_1h,
            bb_list_4h, bb_list_1h,
            macd_list_1d, macd_list_4h, macd_list_1h,
            kdj_list_1d, kdj_list_4h, kdj_list_1h,
            rsi_list_4h, rsi_list_1h)
        return handler.get_sell_direction(self.data.close[0])
