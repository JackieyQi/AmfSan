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
