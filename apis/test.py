#! /usr/bin/env python
# coding:utf8

import time
from decimal import Decimal as D

from models.order import MacdTable
from sanic.views import HTTPMethodView

macd_init_data = {
    "macd_1h": [
        {
            "symbol": "btcusdt",
            "interval": "1h",
            "opening_ts": 1659103200,
            "opening_price": D("23695.41"),
            "closing_price": D("24036.61"),
            "ema_12": D("23844.72"),
            "ema_26": D("23683.35"),
            "dea": D("228.51"),
        },
        {
            "symbol": "btcusdt",
            "interval": "1h",
            "opening_ts": 1659106800,
            "opening_price": D("24034.81"),
            "closing_price": D("24010.74"),
            "ema_12": D("23870.26"),
            "ema_26": D("23707.61"),
            "dea": D("215.34"),
            "macd": D("-52.68"),
        },
    ],
    "macd_4h": [
        {
            "symbol": "btcusdt",
            "interval": "4h",
            "opening_ts": 1659081600,
            "opening_price": D("23941.63"),
            "closing_price": D("23720.56"),
            "ema_12": D("23265.71"),
            "ema_26": D("22749.10"),
            "dea": D("315.61"),
        },
        {
            "symbol": "btcusdt",
            "interval": "4h",
            "opening_ts": 1659096000,
            "opening_price": D("23718.71"),
            "closing_price": D("24010.74"),
            "ema_12": D("23380.33"),
            "ema_26": D("22842.55"),
            "dea": D("360.04"),
            "macd": D("177.72"),
        },
    ],
    "macd_1d": [
        {
            "symbol": "btcusdt",
            "interval": "1d",
            "opening_ts": 1650153600,
            "opening_price": D("40378.70"),
            "closing_price": D("39678.12"),
            "ema_12": D("41340.21"),
            "ema_26": D("42207.85"),
            "dea": D("-330.05"),
        },
        {
            "symbol": "btcusdt",
            "interval": "1d",
            "opening_ts": 1650240000,
            "opening_price": D("39678.11"),
            "closing_price": D("40801.13"),
            "ema_12": D("41257.27"),
            "ema_26": D("42103.64"),
            "dea": D("-433.31"),
            "macd": D("-413.05"),
        },
    ],
}

bnbusdt_macd_init_data = {
    "macd_1h": [
        {
            "symbol": "bnbusdt",
            "interval": "1h",
            "opening_ts": 1661007600,
            "opening_price": D("286.7"),
            "closing_price": D("286.9"),
            "ema_12": D("286.5"),
            "ema_26": D("286.8"),
            "dea": D("-0.8"),
        },
        {
            "symbol": "bnbusdt",
            "interval": "1h",
            "opening_ts": 1661011200,
            "opening_price": D("286.9"),
            "closing_price": D("286.0"),
            "ema_12": D("286.5"),
            "ema_26": D("286.8"),
            "dea": D("-0.7"),
            "macd": D("0.3"),
        },
    ],
    "macd_4h": [
        {
            "symbol": "bnbusdt",
            "interval": "4h",
            "opening_ts": 1661011200,
            "opening_price": D("286.9"),
            "closing_price": D("279.5"),
            "ema_12": D("288.1"),
            "ema_26": D("296.5"),
            "dea": D("-8.0"),
        },
        {
            "symbol": "bnbusdt",
            "interval": "4h",
            "opening_ts": 1661025600,
            "opening_price": D("279.5"),
            "closing_price": D("283.7"),
            "ema_12": D("287.4"),
            "ema_26": D("295.5"),
            "dea": D("-8.0"),
            "macd": D("-0.0"),
        },
    ],
    "macd_1d": [
        {
            "symbol": "bnbusdt",
            "interval": "1d",
            "opening_ts": 1659139200,
            "opening_price": D("293.6"),
            "closing_price": D("287.8"),
            "ema_12": D("267.7"),
            "ema_26": D("257.2"),
            "dea": D("6.7"),
        },
        {
            "symbol": "bnbusdt",
            "interval": "1d",
            "opening_ts": 1659225600,
            "opening_price": D("287.8"),
            "closing_price": D("283.4"),
            "ema_12": D("270.1"),
            "ema_26": D("259.2"),
            "dea": D("7.5"),
            "macd": D("3.3"),
        },
    ],
}

ethusdt_macd_init_data = {
    "macd_1h": [
        {
            "symbol": "ethusdt",
            "interval": "1h",
            "opening_ts": 1661007600,
            "opening_price": D("1633.36"),
            "closing_price": D("1634.69"),
            "ema_12": D("1637.43"),
            "ema_26": D("1661.00"),
            "dea": D("-29.54"),
        },
        {
            "symbol": "ethusdt",
            "interval": "1h",
            "opening_ts": 1661011200,
            "opening_price": D("1634.70"),
            "closing_price": D("1618.80"),
            "ema_12": D("1634.56"),
            "ema_26": D("1657.87"),
            "dea": D("-28.30"),
            "macd": D("4.99"),
        },
    ],
    "macd_4h": [
        {
            "symbol": "ethusdt",
            "interval": "4h",
            "opening_ts": 1661011200,
            "opening_price": D("1634.70"),
            "closing_price": D("1564.23"),
            "ema_12": D("1677.53"),
            "ema_26": D("1751.35"),
            "dea": D("-56.85"),
        },
        {
            "symbol": "ethusdt",
            "interval": "4h",
            "opening_ts": 1661025600,
            "opening_price": D("1564.23"),
            "closing_price": D("1576.04"),
            "ema_12": D("1661.92"),
            "ema_26": D("1738.36"),
            "dea": D("-60.77"),
            "macd": D("-15.66"),
        },
    ],
    "macd_1d": [
        {
            "symbol": "ethusdt",
            "interval": "1d",
            "opening_ts": 1659139200,
            "opening_price": D("1721.68"),
            "closing_price": D("1697.00"),
            "ema_12": D("1570.98"),
            "ema_26": D("1461.01"),
            "dea": D("82.26"),
        },
        {
            "symbol": "ethusdt",
            "interval": "1d",
            "opening_ts": 1659225600,
            "opening_price": D("1697.00"),
            "closing_price": D("1678.12"),
            "ema_12": D("1587.46"),
            "ema_26": D("1477.09"),
            "dea": D("87.88"),
            "macd": D("22.48"),
        },
    ],
}


class MacdInitData(object):
    def init_1h(self):
        data = macd_init_data.get("macd_1h")
        for i in data:
            if MacdTable.select().where(
                MacdTable.opening_ts == i["opening_ts"],
                MacdTable.interval == i["interval"].lower(),
            ):
                print("already")
            else:
                r = MacdTable(
                    symbol=i["symbol"].lower(),
                    interval=i["interval"].lower(),
                    opening_ts=i["opening_ts"],
                    opening_price=i["opening_price"],
                    closing_price=i["closing_price"],
                    ema_12=i["ema_12"],
                    ema_26=i["ema_26"],
                    dea=i["dea"],
                    macd=i["macd"] if "macd" in i else 0,
                    create_ts=int(time.time()),
                ).save()

        db_last_macd = (
            MacdTable.select()
            .where(MacdTable.symbol == "btcusdt", MacdTable.interval == "1h")
            .order_by(MacdTable.create_ts.desc())
            .limit(1)
            .get()
        )
        return db_last_macd.id

    def init_4h(self):
        data = macd_init_data.get("macd_4h")
        for i in data:
            if MacdTable.select().where(
                MacdTable.opening_ts == i["opening_ts"],
                MacdTable.interval == i["interval"].lower(),
            ):
                print("already")
            else:
                r = MacdTable(
                    symbol=i["symbol"].lower(),
                    interval=i["interval"].lower(),
                    opening_ts=i["opening_ts"],
                    opening_price=i["opening_price"],
                    closing_price=i["closing_price"],
                    ema_12=i["ema_12"],
                    ema_26=i["ema_26"],
                    dea=i["dea"],
                    macd=i["macd"] if "macd" in i else 0,
                    create_ts=int(time.time()),
                ).save()

        db_last_macd = (
            MacdTable.select()
            .where(MacdTable.symbol == "btcusdt", MacdTable.interval == "4h")
            .order_by(MacdTable.create_ts.desc())
            .limit(1)
            .get()
        )
        return db_last_macd.id

    def init_1d(self):
        data = macd_init_data.get("macd_1d")
        for i in data:
            if MacdTable.select().where(
                MacdTable.opening_ts == i["opening_ts"],
                MacdTable.interval == i["interval"].lower(),
            ):
                print("already")
            else:
                r = MacdTable(
                    symbol=i["symbol"].lower(),
                    interval=i["interval"].lower(),
                    opening_ts=i["opening_ts"],
                    opening_price=i["opening_price"],
                    closing_price=i["closing_price"],
                    ema_12=i["ema_12"],
                    ema_26=i["ema_26"],
                    dea=i["dea"],
                    macd=i["macd"] if "macd" in i else 0,
                    create_ts=int(time.time()),
                ).save()

        db_last_macd = (
            MacdTable.select()
            .where(MacdTable.symbol == "btcusdt", MacdTable.interval == "1d")
            .order_by(MacdTable.create_ts.desc())
            .limit(1)
            .get()
        )
        return db_last_macd.id


async def get_test(*args, **kwargs):
    a = MacdInitData()
    return a.init_1h(), a.init_4h(), a.init_1d()


class TestView(HTTPMethodView):
    async def get(self, request):
        result = await get_test()
        return "{}".format(result)


class ServerTimeView(HTTPMethodView):
    async def get(self, request):
        return {"ts": time.time(), "dt": time.ctime()}
