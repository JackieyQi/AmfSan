#! /usr/bin/env python
# -*- coding: UTF-8 -*-

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import pandas as pd

from exts import async_database
from models.market import (BollTable, EmaTable, KdjTable, KlineTable, MacdTable, 
                           RsiTable)
from models.factor import CandlestickFactor


class DataLoader:
    """数据加载器，用于获取历史数据和指标数据"""

    @staticmethod
    async def get_historical_data(symbol: str, interval: str, start_time: datetime) -> pd.DataFrame:
        """
        从数据库获取历史K线数据
        
        Args:
            symbol: 交易对
            interval: K线间隔，如 "1h", "4h", "1d"
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            pd.DataFrame: 包含OHLCV数据的DataFrame
        """
        query = KlineTable.select().where(
            KlineTable.symbol == symbol,
            KlineTable.interval_val == interval,
            KlineTable.open_ts >= int(start_time.timestamp())
        )
        
        query = query.order_by(KlineTable.open_ts)
        
        records = list(query)
        if not records:
            return pd.DataFrame()
            
        df = pd.DataFrame([{
            'datetime': datetime.fromtimestamp(r.open_ts),
            'open': float(r.open_price),
            'high': float(r.high_price),
            'low': float(r.low_price),
            'close': float(r.close_price),
            'volume': float(r.volume)
        } for r in records])
        
        df.set_index('datetime', inplace=True)
        return df
        
    @staticmethod
    async def get_indicators(symbol: str, interval: str, start_time: datetime = None, end_time: datetime = None) -> pd.DataFrame:
        """
        从数据库获取技术指标数据
        
        Args:
            symbol: 交易对
            interval: K线间隔
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            Dict[str, pd.DataFrame]: 包含各种技术指标的字典
        """
        # 获取EMA数据
        ema_query = EmaTable.select().where(
            EmaTable.symbol == symbol,
            EmaTable.interval_val == interval
        )
        if start_time:
            ema_query = ema_query.where(EmaTable.open_ts >= int(start_time.timestamp()))
        if end_time:
            ema_query = ema_query.where(EmaTable.open_ts <= int(end_time.timestamp()))
        ema_records = list(ema_query.order_by(EmaTable.open_ts))
        
        # 获取MACD数据
        macd_query = MacdTable.select().where(
            MacdTable.symbol == symbol,
            MacdTable.interval_val == interval
        )
        if start_time:
            macd_query = macd_query.where(MacdTable.opening_ts >= int(start_time.timestamp()))
        if end_time:
            macd_query = macd_query.where(MacdTable.opening_ts <= int(end_time.timestamp()))
        macd_records = await macd_query.order_by(MacdTable.opening_ts.asc()).aio_execute()
        
        # 获取KDJ数据
        kdj_query = KdjTable.select().where(
            KdjTable.symbol == symbol,
            KdjTable.interval_val == interval
        )
        if start_time:
            kdj_query = kdj_query.where(KdjTable.open_ts >= int(start_time.timestamp()))
        if end_time:
            kdj_query = kdj_query.where(KdjTable.open_ts <= int(end_time.timestamp()))
        kdj_records = list(kdj_query.order_by(KdjTable.open_ts))
        
        # 获取RSI数据
        rsi_query = RsiTable.select().where(
            RsiTable.symbol == symbol,
            RsiTable.interval_val == interval
        )
        if start_time:
            rsi_query = rsi_query.where(RsiTable.open_ts >= int(start_time.timestamp()))
        if end_time:
            rsi_query = rsi_query.where(RsiTable.open_ts <= int(end_time.timestamp()))
        rsi_records = list(rsi_query.order_by(RsiTable.open_ts))
        
        # 获取布林带数据
        boll_query = BollTable.select().where(
            BollTable.symbol == symbol,
            BollTable.interval_val == interval
        )
        if start_time:
            boll_query = boll_query.where(BollTable.open_ts >= int(start_time.timestamp()))
        if end_time:
            boll_query = boll_query.where(BollTable.open_ts <= int(end_time.timestamp()))
        boll_records = list(boll_query.order_by(BollTable.open_ts))
        
        # 合并所有指标数据
        indicators = {}
        
        # 添加EMA指标
        if ema_records:
            indicators['ema_short'] = [float(r.ema_short) for r in ema_records]
            indicators['ema_mid'] = [float(r.ema_mid) for r in ema_records]
            indicators['ema_long'] = [float(r.ema_long) for r in ema_records]
            
        # 添加MACD指标
        if macd_records:
            indicators['macd'] = [float(r.macd) for r in macd_records]
            indicators['macd_signal'] = [float(r.macd_signal) for r in macd_records]
            indicators['macd_hist'] = [float(r.macd_hist) for r in macd_records]
            
        # 添加KDJ指标
        if kdj_records:
            indicators['k'] = [float(r.k) for r in kdj_records]
            indicators['d'] = [float(r.d) for r in kdj_records]
            indicators['j'] = [float(r.j) for r in kdj_records]
            
        # 添加RSI指标
        if rsi_records:
            indicators['rsi'] = [float(r.rsi) for r in rsi_records]
            
        # 添加布林带指标
        if boll_records:
            indicators['boll_upper'] = [float(r.boll_upper) for r in boll_records]
            indicators['boll_mid'] = [float(r.boll_mid) for r in boll_records]
            indicators['boll_lower'] = [float(r.boll_lower) for r in boll_records]
            
        return pd.DataFrame(indicators)
        
    @staticmethod
    def merge_data_and_indicators(data: pd.DataFrame, indicators: pd.DataFrame) -> pd.DataFrame:
        """
        合并K线数据和技术指标数据
        
        Args:
            data: K线数据DataFrame
            indicators: 技术指标DataFrame
            
        Returns:
            DataFrame: 合并后的数据
        """
        if data.empty or indicators.empty:
            return pd.DataFrame()
            
        return pd.concat([data, indicators], axis=1)
        
    @staticmethod
    def load_from_external_data(kline_list: list, macd_list: list = None, bb_list: list = None) -> pd.DataFrame:
        """
        从外部数据源加载数据
        
        Args:
            kline_list: K线数据列表
            macd_list: MACD数据列表
            bb_list: 布林带数据列表
            
        Returns:
            DataFrame: 合并后的数据
        """
        # 转换K线数据
        df = pd.DataFrame([{
            'datetime': datetime.fromtimestamp(k['open_ts']),
            'open': float(k['open_price']),
            'high': float(k['high_price']),
            'low': float(k['low_price']),
            'close': float(k['close_price']),
            'volume': float(k['volume'])
        } for k in kline_list])
        
        df.set_index('datetime', inplace=True)
        
        # 如果有MACD数据，添加到DataFrame
        if macd_list:
            macd_df = pd.DataFrame([{
                'datetime': datetime.fromtimestamp(m['open_ts']),
                'macd': float(m['macd']),
                'macd_signal': float(m['macd_signal']),
                'macd_hist': float(m['macd_hist'])
            } for m in macd_list])
            macd_df.set_index('datetime', inplace=True)
            df = pd.concat([df, macd_df], axis=1)
            
        # 如果有布林带数据，添加到DataFrame
        if bb_list:
            bb_df = pd.DataFrame([{
                'datetime': datetime.fromtimestamp(b['open_ts']),
                'boll_upper': float(b['boll_upper']),
                'boll_mid': float(b['boll_mid']),
                'boll_lower': float(b['boll_lower'])
            } for b in bb_list])
            bb_df.set_index('datetime', inplace=True)
            df = pd.concat([df, bb_df], axis=1)
            
        return df

    @staticmethod
    def resample_data(df: pd.DataFrame, timeframe: str = '1H') -> pd.DataFrame:
        """
        重采样数据到指定的时间周期
        
        Args:
            df: 原始数据
            timeframe: 时间周期，例如 '1H', '4H', '1D' 等
            
        Returns:
            pd.DataFrame: 重采样后的数据
        """
        if df.empty:
            return df
            
        resampled = df.resample(timeframe).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        })
        
        return resampled.dropna()
