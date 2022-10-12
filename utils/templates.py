#! /usr/bin/env python
# coding:utf8

from utils.common import decimal2str, ts2bjfmt


def template_macd_cross_notice(
    symbol, interval, last_macd, new_macd, opening_ts, history_macd_list
):
    return f"""
            <br><br><b> {symbol.upper()}: </b>
            <br> macd cross changing:
            <br>interval: {interval},
            <br>last macd to new macd: <b>{decimal2str(last_macd)} -> {decimal2str(new_macd)}</b>,
            <br>last change array: {history_macd_list},
            <br>opening time:{ts2bjfmt(opening_ts)}
            """


def template_macd_trend_notice(
    symbol, interval, last_macd, new_macd, trend_val, opening_ts, history_macd_list
):
    return f"""
            <br><br><b> {symbol.upper()}: </b>
            <br> macd trend notice:
            <br>interval: {interval},
            <br>macd trend: <b>{decimal2str(last_macd)} ->{trend_val}-> {decimal2str(new_macd)}</b>,
            <br>last change array: {history_macd_list},
            <br>opening time:{ts2bjfmt(opening_ts)}
            """


def template_asset_notice(price, btc_val, usdt_val, create_ts, profit_amount, profit_ratio):
    return f"""
            <br><br> {ts2bjfmt(create_ts)}: {profit_amount}/{profit_ratio}
            <br> PRICE:{price}, BTC:{btc_val}, USDT:{usdt_val}.
            """
