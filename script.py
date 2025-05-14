#! /usr/bin/env python
# coding:utf8

import json
from decimal import Decimal as D
import asyncio
import click
from datetime import datetime, timedelta

from cache import RedisPoolContext
from exts import MysqlClient
from models import order, user, wallet, market
from business.backtest.backtest_engine import BacktestEngine
from business.backtest.backtest_strategy import BacktestStrategy
from business.backtest.data_loader import DataLoader

database = MysqlClient.get_database()


@click.group()
def cli():
    pass


@cli.command()
def cmd_test():
    print("test")


@cli.command()
def cmd_create_tables():
    """
    创建表
    """
    print("***************start command_create_tables**************")
    with database:
        database.create_tables(
            [
                order.SymbolPriceChangeHistoryTable,
                order.OrderTradeHistoryTable,
                order.PlotBackTestTable,
                wallet.BalanceHistoryTable,
                wallet.TotalBalanceHistoryTable,
                user.EmailMsgHistoryTable,
                user.UserInfoTable,
                user.UserSymbolPlotTable,
                market.KlineTable,
                market.MacdTable,
                market.KdjTable,
                market.RsiTable,
                market.BollTable,
                market.BnSymbolTable,
            ]
        )

    print("***************end command_create_tables****************")


def command_update_tables():
    from peewee import CharField
    from playhouse.migrate import MySQLMigrator, migrate

    print("***************start command_update_tables**************")

    order_id_field = CharField(default=0)
    migrator = MySQLMigrator(database)
    with database.atomic():
        migrate(
            # migrator.add_column(
            #     "order_trade_history_table", "order_id", order_id_field
            # ),
            migrator.rename_column("macd_table", "interval", "interval_val"),
        )

    print("***************end command_update_tables****************")


def command_insert_mytrades(key, secret, symbol):
    from business.binance_exchange import BinanceExchangeRequestHandle
    from models.order import OrderTradeHistoryTable

    print("***************start command_insert_mytrades**************")

    symbol = symbol.lower()
    trades_data = BinanceExchangeRequestHandle(key, secret).get_my_trades(
        symbol.upper()
    )
    count = 0
    for i in trades_data:
        _trade_id = i["id"]

        if OrderTradeHistoryTable.select().where(
                OrderTradeHistoryTable.trade_id == _trade_id
        ):
            continue

        _ = OrderTradeHistoryTable(
            user_id=2,
            trade_id=_trade_id,
            order_id=i["orderId"],
            symbol=i["symbol"].lower(),
            price=D(i["price"]),
            qty=D(i["qty"]),
            quote_qty=D(i["quoteQty"]),
            trade_ts=int(i["time"] / 1000),
            is_buyer=i["isBuyer"],
            is_maker=i["isMaker"],
            extra_data=json.dumps(i),
        ).save()
        count += 1

    print(f"Insert data count {count}")
    print("***************end command_insert_mytrades****************")


def command_del_symbol(symbol):
    from models.user import UserSymbolPlotTable
    from models.market import KlineTable, MacdTable, KdjTable, RsiTable
    from cache import AllCache

    print("***************start command_add_new_symbol**************")
    symbol = symbol.lower()

    symbol_plot_del_rows = UserSymbolPlotTable.delete().where(
        UserSymbolPlotTable.user_id == "root", UserSymbolPlotTable.symbol == symbol
    ).execute()

    kline_del_rows = KlineTable.delete().where(KlineTable.symbol==symbol).execute()
    macd_del_rows = MacdTable.delete().where(MacdTable.symbol==symbol).execute()
    kdj_del_rows = KdjTable.delete().where(KdjTable.symbol==symbol).execute()
    rsi_del_rows = RsiTable.delete().where(RsiTable.symbol==symbol).execute()

    redis_client = AllCache.get_client()
    redis_key = "symbol:cfg"
    redis_client.delete(redis_key)
    redis_client.close()

    print(f"删除数据："
          f"\nsymbol_plot_del_rows:{symbol_plot_del_rows}"
          f"\nkline_del_rows:{kline_del_rows}"
          f"\nmacd_del_rows:{macd_del_rows}"
          f"\nkdj_del_rows:{kdj_del_rows}"
          f"\nrsi_del_rows:{rsi_del_rows}")

    print("***************end command_add_new_symbol****************")


@cli.command()
@click.option('--email', required=True)
@click.option('--code', required=True, help='邀请码(6位字符串)')
def cmd_set_invite_code(email: str, code: str):
    """
    设置邀请码
    
    Args:
        email: 邮箱
        code: 邀请码(6位字符串)
    """
    print("***************start command_set_invite_code**************")

    with RedisPoolContext() as r:
        r.set(f"user:invite_code:{email}", code, ex=600)

    print(f"设置邀请码成功，有效期10分钟")
    print("*************** end ****************")


@cli.command()
@click.option('--symbol', required=True, help='交易对，例如：belusdt')
@click.option('--valid', required=True, help='是否有效，0: 无效，1: 有效')
def cmd_cancel_symbol_check_price(symbol: str, valid: bool):
    """
    取消交易对价格检查
    
    Args:
        symbol: 交易对
        valid: 是否有效(0/1)
    """

    print("*************** start **************")
    
    try:
        symbol = symbol.lower().strip()
        valid = False if int(valid) == 0 else True
    except Exception as e:
        print(f"错误：{e}")
        return
    
    update_str = ""
    old_symbol = market.BnSymbolTable.select().where(
        market.BnSymbolTable.symbol == symbol).first()
    if old_symbol:
        old_symbol.is_valid = valid
        old_symbol.save()
        update_str = "更新"
    else:
        market.BnSymbolTable(symbol=symbol, is_valid=valid).save()
        update_str = "新增"

    valid_count = market.BnSymbolTable.select().where(
        market.BnSymbolTable.is_valid).count()
    print(f"{update_str} {symbol} 成功，当前有效交易对数量: {valid_count}")
    print("*************** end ****************")


@cli.command()
@click.option('--symbol', required=True, help='交易对，例如：btcusdt')
@click.option('--start_time', default=None, help='开始时间，格式：YYYY-MM-DD_HH:mm，例如：2024-05-10_05:00')
def cmd_backtest_strategy(symbol: str, start_time: str):
    """
    回测策略
    
    Args:
        symbol: 交易对
        start_time: 开始时间
    """
    async def run_backtest():
        # 创建回测引擎
        engine = BacktestEngine()
        
        # 设置回测时间范围
        end_time_dt = datetime.now()
        try:
            if start_time:
                start_time_dt = datetime.strptime(start_time, '%Y-%m-%d_%H:%M')
            else:
                # 如果没有指定开始时间，默认回测最近30天
                start_time_dt = end_time_dt - timedelta(days=30)
                
            if start_time_dt >= end_time_dt:
                click.echo("错误：开始时间必须早于结束时间")
                return
                
        except ValueError as e:
            click.echo(f"错误：时间格式不正确，请使用 YYYY-MM-DD_HH:mm 格式，例如：2024-05-10_05:00")
            return
        
        data_loader = DataLoader()
        interval = "1h"
        kline_data = await data_loader.get_historical_data(symbol, interval, start_time_dt)
        
        if kline_data.empty:
            click.echo(f"没有找到 {symbol} 在 {interval} 周期下的历史数据")
            return
            
        # 添加数据到引擎
        engine.add_data(kline_data)
        
        # 添加策略
        engine.add_strategy(BacktestStrategy, symbol=symbol)
            
        # 设置初始资金和佣金
        engine.set_cash(10000)
        engine.set_commission(0.001)
        
        # 运行回测
        engine.run()
        
        # 获取结果
        results = engine.get_results()
        
        # 打印回测结果
        click.echo("\n=== 回测结果 ===")
        click.echo(f"交易对: {symbol}")
        # click.echo(f"时间周期: {interval}")
        click.echo(f"回测时间: {start_time_dt.strftime('%Y-%m-%d %H:%M')} 到 {end_time_dt.strftime('%Y-%m-%d %H:%M')}")
        # click.echo(f"初始资金: {initial_cash:.2f}")
        # click.echo(f"最终资金: {results['portfolio_value']:.2f}")
        click.echo(f"总收益率: {results['returns']*100:.2f}%")
        click.echo(f"最大回撤: {results['drawdown']['max_drawdown_percent']:.2f}%")
        click.echo(f"交易次数: {len(results['trades'])}")
        
        # 计算胜率
        if results['trades']:
            winning_trades = sum(1 for trade in results['trades'] if trade['pnl'] > 0)
            win_rate = winning_trades / len(results['trades']) * 100
            click.echo(f"胜率: {win_rate:.2f}%")
        
        # 绘制图表
        engine.plot()

    # 运行回测
    asyncio.run(run_backtest())


if __name__ == "__main__":
    print("RUN: script.")
    cli()
