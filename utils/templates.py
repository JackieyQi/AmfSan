#! /usr/bin/env python
# coding:utf8

from settings.constants import (INNER_GET_DELETE_MACD_CROSS_URL,
                                INNER_GET_DELETE_MACD_TREND_URL,
                                INNER_GET_DELETE_KDJ_CROSS_URL,)

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
            <br>
            <br><a href={INNER_GET_DELETE_MACD_CROSS_URL}{symbol + '_' + interval}>Delete cross check.</a>
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
            <br>
            <br><a href={INNER_GET_DELETE_MACD_TREND_URL}{symbol + '_' + interval}>Delete trend check.</a>
            """


def template_kdj_cross_notice(
    symbol, interval, cross_str, macd_list, open_ts
):
    return f"""
            <br><br><b> {symbol.upper()}: </b>
            <br> kdj cross changing:
            <br>interval: {interval},
            <br>cross result: <b>{cross_str}</b>,
            <br>macd array: <b>{macd_list}</b>,
            <br>opening time:{ts2bjfmt(open_ts)}
            <br>
            <br><a href={INNER_GET_DELETE_KDJ_CROSS_URL}{symbol + '_' + interval}>Delete cross check.</a>
            """


def template_asset_notice(
    price, btc_val, usdt_val, create_ts, profit_amount, profit_ratio
):
    return f"""
            <br><br> {ts2bjfmt(create_ts)}: {profit_amount}/{profit_ratio}
            <br> PRICE:{price}, BTC:{btc_val}, USDT:{usdt_val}.
            """
