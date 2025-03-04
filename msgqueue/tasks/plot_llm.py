#! /usr/bin/env python
# -*- coding: UTF-8 -*-

import json
from decimal import Decimal
from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.schema import AgentAction, AgentFinish, HumanMessage, SystemMessage

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
                "open_time": int(kline.open_ts),
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
                "type": volume_type,
                "open_time": int(kline.open_ts),
            })

            # 添加MACD数据
            if macd:
                macd_array.append({
                    "dif": decimal2str(macd.ema_12 - macd.ema_26),  # DIF = EMA12 - EMA26
                    "dea": decimal2str(macd.dea),
                    "macd": decimal2str(macd.macd),
                    "open_time": int(kline.open_ts),
                })

            # 添加KDJ数据
            kdj = kdj_dict.get(kline.open_ts)
            if kdj:
                kdj_array.append({
                    "k_val": decimal2str(kdj.k_val),
                    "d_val": decimal2str(kdj.d_val),
                    "j_val": decimal2str(kdj.j_val),
                    "open_time": int(kline.open_ts),
                })

        return {
            "price_array": price_array,
            "volume_array": volume_array,
            "macd_array": macd_array,
            "kdj_array": kdj_array
        }


class MarketAnalysisAgent(object):
    def __init__(self, openai_api_key):
        self.llm = ChatOpenAI(
            temperature=0,
            model_name="gpt-4",
            openai_api_key=openai_api_key,
        )

        self.memories = {
            "1d": ConversationBufferMemory(memory_key="1d_analysis"),
            "4h": ConversationBufferMemory(memory_key="4h_analysis"),
            "1h": ConversationBufferMemory(memory_key="1h_analysis"),
        }

        self.market_data = LlmMarketData()

    def __create_analysis_prompt(self):
        return """
        你是一个专业的加密货币交易分析师。基于提供的市场数据进行分析，输出买入、卖出或持仓的建议概率。
        
        当前数据包含:
        1. K线数据：开盘价、最高价、最低价、收盘价
        2. 交易量数据
        3. MACD指标：DIF、DEA、MACD
        4. KDJ指标：K值、D值、J值
        
        请分析这些数据，并给出以下形式的回答：
        {
            "buy_probability": float,  # 买入概率 (0-1)
            "sell_probability": float, # 卖出概率 (0-1)
            "hold_probability": float, # 持仓概率 (0-1)
            "analysis": string,       # 分析理由
            "risk_level": string     # 风险等级 (low/medium/high)
        }
        
        历史分析记录:
        {history}
        
        当前时间周期: {interval}
        请分析当前市场数据:
        {market_data}
        """

    def __format_market_data(self, data):
        """格式化市场数据为易读的字符串"""
        if not data:
            return "No data available"

        latest_price = data["price_array"][-1]
        latest_macd = data["macd_array"][-1] if data["macd_array"] else None
        latest_kdj = data["kdj_array"][-1] if data["kdj_array"] else None

        formatted_data = f"""
        最新价格数据:
        - 开盘价: {latest_price['open_price']}
        - 最高价: {latest_price['high_price']}
        - 最低价: {latest_price['low_price']}
        - 收盘价: {latest_price['close_price']}
        """

        if latest_macd:
            formatted_data += f"""
        MACD指标:
        - DIF: {latest_macd['dif']}
        - DEA: {latest_macd['dea']}
        - MACD: {latest_macd['macd']}
        """

        if latest_kdj:
            formatted_data += f"""
        KDJ指标:
        - K值: {latest_kdj['k_val']}
        - D值: {latest_kdj['d_val']}
        - J值: {latest_kdj['j_val']}
        """

        return formatted_data

    async def analyze_market(self, symbol, interval):
        market_data = self.market_data.get_market_data(symbol, interval)
        if not market_data:
            return {"error": "No market data available"}

        memory = self.memories[interval]
        history = memory.load_memory_variables({})

        formatted_data = self.__format_market_data(market_data)
        prompt = self.__create_analysis_prompt().format(
            history=history.get(memory.memory_key, "No previous analysis"),
            interval=interval,
            market_data=formatted_data,
        )

        # 调用LLM进行分析
        messages = [
            SystemMessage(content="You are a professional cryptocurrency trading analyst."),
            HumanMessage(content=prompt)
        ]
        response = await self.llm.agenerate([messages])

        analysis_result = json.loads(response.generations[0][0].text)
        # 验证概率总和是否为1
        probabilities = [
            analysis_result["buy_probability"],
            analysis_result["sell_probability"],
            analysis_result["hold_probability"]
        ]

        if abs(sum(probabilities) - 1.0) > 0.01:
            raise ValueError("Probabilities must sum to 1")

        memory.save_context(
            {"input": f"Market analysis for {interval}"},
            {"output": json.dumps(analysis_result, indent=2)}
        )

        return analysis_result

    async def analyze_all_intervals(self, symbol):
        result = {}
        for interval in ["1d", "4h", "1h"]:
            result[interval] = await self.analyze_market(symbol, interval)
        return result
