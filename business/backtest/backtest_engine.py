#! /usr/bin/env python
# coding:utf8

import backtrader as bt
import pandas as pd
from datetime import datetime
from typing import Type, Dict, Any


class BacktestEngine:
    """回测引擎，用于管理和执行回测策略"""
    
    def __init__(self):
        """
        初始化回测引擎
        """
        self.cerebro = bt.Cerebro()
        self.data = None
        self.strategy = None
        self.results = None
        
    def add_data(self, data: pd.DataFrame):
        """
        添加数据到回测引擎
        
        Args:
            data: 包含OHLCV和指标数据的DataFrame
        """
        if data.empty:
            raise ValueError("数据为空")
            
        # 创建backtrader数据源
        data_feed = bt.feeds.PandasData(
            dataname=data,
            datetime=None,  # 使用索引作为日期时间
            open='open',
            high='high',
            low='low',
            close='close',
            volume='volume',
            openinterest=-1
        )
        
        self.cerebro.adddata(data_feed)
        self.data = data
        
    def add_strategy(self, strategy_class: Type[bt.Strategy], **kwargs):
        """
        添加策略到回测引擎
        
        Args:
            strategy_class: 策略类
            **kwargs: 策略参数
        """
        self.cerebro.addstrategy(strategy_class, **kwargs)
        self.strategy = strategy_class
        
    def set_cash(self, cash: float):
        """
        设置初始资金
        
        Args:
            cash: 初始资金
        """
        self.cerebro.broker.setcash(cash)
        
    def set_commission(self, commission: float):
        """
        设置交易佣金
        
        Args:
            commission: 佣金比例
        """
        self.cerebro.broker.setcommission(commission=commission)
        
    def run(self):
        """
        运行回测
        """
        self.results = self.cerebro.run()
        
    def get_results(self) -> Dict[str, Any]:
        """
        获取回测结果
        
        Returns:
            Dict: 包含回测结果的字典
        """
        if not self.results:
            raise ValueError("请先运行回测")
            
        # 获取策略实例
        strategy = self.results[0]
        
        # 获取投资组合价值
        portfolio_value = self.cerebro.broker.getvalue()
        
        # 计算收益率
        initial_cash = self.cerebro.broker.startingcash
        returns = (portfolio_value - initial_cash) / initial_cash
        
        # 获取交易记录
        trades = []
        for trade in strategy.analyzers.tradeanalyzer.get_analysis()['trades']:
            trades.append({
                'entry_date': trade.dtopen,
                'exit_date': trade.dtclose,
                'entry_price': trade.price,
                'exit_price': trade.pnl,
                'pnl': trade.pnl,
                'pnlcomm': trade.pnlcomm
            })
            
        # 获取回撤信息
        drawdown = {
            'max_drawdown': strategy.analyzers.drawdown.get_analysis()['max']['drawdown'],
            'max_drawdown_percent': strategy.analyzers.drawdown.get_analysis()['max']['drawdown_percent'],
            'max_drawdown_length': strategy.analyzers.drawdown.get_analysis()['max']['len']
        }
        
        return {
            'portfolio_value': portfolio_value,
            'returns': returns,
            'trades': trades,
            'drawdown': drawdown
        }
        
    def plot(self):
        """
        绘制回测结果图表
        """
        self.cerebro.plot()
        
    def add_external_strategy(self, strategy_instance: Any, **kwargs):
        """
        添加外部策略实例
        
        Args:
            strategy_instance: 外部策略实例
            **kwargs: 策略参数
        """
        # 创建backtrader策略包装器
        class StrategyWrapper(bt.Strategy):
            params = kwargs
            
            def __init__(self):
                self.strategy = strategy_instance
                self.order = None
                
            def next(self):
                # 调用外部策略的is_detected方法
                signal = self.strategy.is_detected()
                
                if signal == 1:  # 买入信号
                    if not self.position:
                        self.order = self.buy()
                elif signal == -1:  # 卖出信号
                    if self.position:
                        self.order = self.sell()
                        
        self.cerebro.addstrategy(StrategyWrapper)
        self.strategy = StrategyWrapper 
