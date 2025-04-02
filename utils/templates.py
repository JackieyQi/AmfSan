#! /usr/bin/env python
# coding:utf8

from settings.constants import (INNER_GET_DELETE_MACD_CROSS_URL,
                                INNER_GET_DELETE_MACD_TREND_URL,
                                INNER_GET_DELETE_KDJ_CROSS_URL,)

from utils.common import decimal2str, ts2bjfmt


def template_macd_cross_notice(
    symbol, interval, cross_str, opening_ts, current_history_macd_list, btc_kdj_list, btc_history_macd_list
):
    return f"""
            <br><br><b> {symbol.upper()}: </b>
            <br> <b>macd</b> cross:
            <br>{interval},
            <br><b>{cross_str}</b>,
            <br>
            <br>opening time:{ts2bjfmt(opening_ts)}
            <table border="1">
            <tr>
                <td></td><td>5m</td><td>15m</td><td>1h</td><td>4h</td><td>1d</td>
            </tr>
            <tr>
                <td>MACD: {symbol.upper()}</td>
                <td>{current_history_macd_list["5m"]}</td>
                <td>{current_history_macd_list["15m"]}</td>
                <td>{current_history_macd_list["1h"]}</td>
                <td>{current_history_macd_list["4h"]}</td>
                <td>{current_history_macd_list["1d"]}</td>
            </tr>
            <tr>
                <td>KDJ : BTCUSDT</td>
                <td>{btc_kdj_list["5m"]}</td>
                <td>{btc_kdj_list["15m"]}</td>
                <td>{btc_kdj_list["1h"]}</td>
                <td>{btc_kdj_list["4h"]}</td>
                <td>{btc_kdj_list["1d"]}</td>
            </tr>
            <tr>
                <td>MACD: BTCUSDT</td>
                <td>{btc_history_macd_list["5m"]}</td>
                <td>{btc_history_macd_list["15m"]}</td>
                <td>{btc_history_macd_list["1h"]}</td>
                <td>{btc_history_macd_list["4h"]}</td>
                <td>{btc_history_macd_list["1d"]}</td>
            </tr>
            </table>
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
    symbol, interval, cross_str, new_macd_list, btc_kdj_list, btc_macd_list, open_ts
):
    return f"""
            <br><br><b> {symbol.upper()}: </b>
            <br> <b>kdj</b> cross:
            <br>{interval},
            <br><b>{cross_str}</b>,
            <br>
            <br>opening time:{ts2bjfmt(open_ts)}
            <table border="1">
            <tr>
                <td></td><td>5m</td><td>15m</td><td>1h</td><td>4h</td><td>1d</td>
            </tr>
            <tr>
                <td>MACD: {symbol.upper()}</td>
                <td>{new_macd_list["5m"]}</td>
                <td>{new_macd_list["15m"]}</td>
                <td>{new_macd_list["1h"]}</td>
                <td>{new_macd_list["4h"]}</td>
                <td>{new_macd_list["1d"]}</td>
            </tr>
            <tr>
                <td>KDJ : BTCUSDT</td>
                <td>{btc_kdj_list["5m"]}</td>
                <td>{btc_kdj_list["15m"]}</td>
                <td>{btc_kdj_list["1h"]}</td>
                <td>{btc_kdj_list["4h"]}</td>
                <td>{btc_kdj_list["1d"]}</td>
            </tr>
            <tr>
                <td>MACD: BTCUSDT</td>
                <td>{btc_macd_list["5m"]}</td>
                <td>{btc_macd_list["15m"]}</td>
                <td>{btc_macd_list["1h"]}</td>
                <td>{btc_macd_list["4h"]}</td>
                <td>{btc_macd_list["1d"]}</td>
            </tr>
            </table>
            <br>
            <br><a href={INNER_GET_DELETE_KDJ_CROSS_URL}{symbol + '_' + interval}>Delete cross check.</a>
            """


def template_ema_cross_notice(
    symbol, interval, cross_str, open_ts
):
    return f"""
            <br><br><b> {symbol.upper()}: </b>
            <br> <b>ema</b> cross:
            <br>{interval},
            <br><b>{cross_str}</b>,
            <br>
            <br>opening time:{ts2bjfmt(open_ts)}
            <br>
            <br><a href=>Delete cross check.</a>
            """


def template_asset_notice(
    price, btc_val, usdt_val, create_ts, profit_amount, profit_ratio
):
    return f"""
            <br><br> {ts2bjfmt(create_ts)}: {profit_amount}/{profit_ratio}
            <br> PRICE:{price}, BTC:{btc_val}, USDT:{usdt_val}.
            """


def template_gpt_plot_trend_following_strategy_notice(symbol, direction, open_ts):
    return f"""
            <br><br><b> 🔥Trend following strategy: {symbol.upper()}: </b> <b>{direction}</b>
            <br>opening time:{ts2bjfmt(open_ts)}
            """


def template_gpt_plot_short_term_strategy_notice(
        symbol, direction, open_ts, current_price, send_ts, close_url, set_url):
    # 避免邮件客户端的安全限制可能会阻止JavaScript的执行，全部使用直接链接
    return f"""
            <div>
            <br><br>❓(待优化) <b>{symbol.upper()}</b>: {direction}
            <br>当前价: {current_price}, 发送时间：{ts2bjfmt(send_ts)}
            <br>opening time:{ts2bjfmt(open_ts)}
            </div>
            
            <div style='margin-top: 20px;'>
            <a href='{close_url}'
               style='display: inline-block; padding: 10px 20px; margin-right: 10px; 
                      background-color: #4CAF50; color: white; text-decoration: none; 
                      border-radius: 4px;'>
                删除监控
            </a>
            
            <a href='{set_url}' 
               style='display: inline-block; padding: 10px 20px; 
                      background-color: #008CBA; color: white; text-decoration: none; 
                      border-radius: 4px;'>
                设置限价
            </a>
            </div>
            """


def template_gpt_plot_bull_run_strategy_notice(
        symbol, direction, open_ts, current_price, send_ts, close_monitor_url, set_limit_price_url):
    return f"""
            <div>
            <br><br><b> 📝4小时连续破高上涨 {symbol.upper()}</b>: {direction}
            <br>当前价: {current_price}, 发送时间：{ts2bjfmt(send_ts)}
            <br>opening time:{ts2bjfmt(open_ts)}
            </div>
            
                        <div style='margin-top: 20px;'>
            <a href='{close_monitor_url}'
               style='display: inline-block; padding: 10px 20px; margin-right: 10px; 
                      background-color: #4CAF50; color: white; text-decoration: none; 
                      border-radius: 4px;'>
                删除监控
            </a>
            
            <a href='{set_limit_price_url}' 
               style='display: inline-block; padding: 10px 20px; 
                      background-color: #008CBA; color: white; text-decoration: none; 
                      border-radius: 4px;'>
                设置限价
            </a>
            </div>
            """


def template_strategy_notice(
        direction, open_ts, current_price, send_ts, close_monitor_url, set_limit_price_url):
    return f"""
            <div>
            <br>{direction}
            <br>
            <br>当前价: {current_price}, 发送时间：{ts2bjfmt(send_ts)}
            <br>open time:{ts2bjfmt(open_ts)}
            </div>

                        <div style='margin-top: 20px;'>
            <a href='{close_monitor_url}'
               style='display: inline-block; padding: 10px 20px; margin-right: 10px; 
                      background-color: #4CAF50; color: white; text-decoration: none; 
                      border-radius: 4px;'>
                删除监控
            </a>

            <a href='{set_limit_price_url}' 
               style='display: inline-block; padding: 10px 20px; 
                      background-color: #008CBA; color: white; text-decoration: none; 
                      border-radius: 4px;'>
                设置限价
            </a>
            </div>
            """
