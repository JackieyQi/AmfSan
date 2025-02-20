#! /usr/bin/env python
# -*- coding: UTF-8 -*-

from decimal import Decimal
from utils.common import decimal2str
from models.market import KlineTable
from models.order import MacdTable, KdjTable


class LlmMarketData(object):
    def __init__(self):
        self.limit_count = 40

    def get_market_data(self, symbol: str, interval: str):
        # 1. 获取最近40条K线数据
        klines = (KlineTable
                  .select()
                  .where(
            KlineTable.symbol == symbol,
            KlineTable.interval_val == interval
        )
                  .order_by(KlineTable.open_ts.desc())
                  .limit(self.limit_count)
                  .execute())

        if not klines:
            return

        # 获取时间范围
        klines = list(klines)
        start_ts = min(k.open_ts for k in klines)
        end_ts = max(k.open_ts for k in klines)

        # 2. 获取对应时间范围的MACD数据
        macds = (MacdTable
                 .select()
                 .where(
            MacdTable.symbol == symbol,
            MacdTable.interval_val == interval,
            MacdTable.opening_ts >= start_ts,
            MacdTable.opening_ts <= end_ts
        )
                 .order_by(MacdTable.opening_ts.asc())
                 .execute())

        # 3. 获取对应时间范围的KDJ数据
        kdjs = (KdjTable
                .select()
                .where(
            KdjTable.symbol == symbol,
            KdjTable.interval_val == interval,
            KdjTable.open_ts >= start_ts,
            KdjTable.open_ts <= end_ts
        )
                .order_by(KdjTable.open_ts.asc())
                .execute())

        # 4. 构建返回数据
        price_array = []
        volume_array = []
        macd_array = []
        kdj_array = []

        # 创建时间映射的字典
        macd_dict = {m.opening_ts: m for m in macds}
        kdj_dict = {k.open_ts: k for k in kdjs}

        # 按时间递增排序K线数据
        for kline in sorted(klines, key=lambda x: x.open_ts):
            # 添加价格数据
            price_data = {
                "open_price": decimal2str(kline.open_price),
                "high_price": decimal2str(kline.high_price),
                "close_price": decimal2str(kline.close_price),
                "low_price": decimal2str(kline.low_price),
            }

            # 添加EMA数据（如果存在对应的MACD记录）
            macd = macd_dict.get(kline.open_ts)
            if macd:
                price_data["ema12"] = decimal2str(macd.ema_12)
                price_data["ema26"] = decimal2str(macd.ema_26)

            price_array.append(price_data)

            # 添加交易量数据（根据买入量判断主导方向）
            volume_type = "buy" if kline.buy_volume > (kline.volume - kline.buy_volume) else "sell"
            volume_array.append({
                "volume": decimal2str(kline.volume),
                "type": volume_type
            })

            # 添加MACD数据
            if macd:
                macd_array.append({
                    "dif": decimal2str(macd.ema_12 - macd.ema_26),  # DIF = EMA12 - EMA26
                    "dea": decimal2str(macd.dea),
                    "macd": decimal2str(macd.macd)
                })

            # 添加KDJ数据
            kdj = kdj_dict.get(kline.open_ts)
            if kdj:
                kdj_array.append({
                    "k_val": decimal2str(kdj.k_val),
                    "d_val": decimal2str(kdj.d_val),
                    "j_val": decimal2str(kdj.j_val)
                })

        return {
            "price_array": price_array,
            "volume_array": volume_array,
            "macd_array": macd_array,
            "kdj_array": kdj_array
        }
