#! /usr/bin/env python
# coding:utf8

import time
from models.order import SymbolPlotTable
from settings.constants import PLOT_INTERVAL_LIST
from cache.plot import CheckMacdCrossGateCache
from msgqueue.tasks.plot import PlotMacdHandle


def main():
    print("Start plot script: check_macd_cross_job")
    while 1:
        query = SymbolPlotTable.select().where(SymbolPlotTable.is_valid == True)
        for row in query:
            for _interval in PLOT_INTERVAL_LIST:
                if not CheckMacdCrossGateCache.hget(f"{row.symbol}:{_interval}"):
                    continue
                PlotMacdHandle(row.symbol, _interval).check_cross_unsync()

        time.sleep(70)


if __name__ == "__main__":
    main()
