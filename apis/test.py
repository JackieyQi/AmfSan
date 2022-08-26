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
