#! /usr/bin/env python
# coding:utf8

import time
from models.order import SymbolPlotTable
from settings.constants import PLOT_INTERVAL_LIST
from cache.plot import CheckKdjCrossGateCache
from msgqueue.tasks.plot import PlotKdjHandle


def main():
    print("Start plot script: check_kdj_cross_job")
    while 1:
        query = SymbolPlotTable.select().where(SymbolPlotTable.is_valid == True)
        for row in query:
            for _interval in PLOT_INTERVAL_LIST:
                if not CheckKdjCrossGateCache.hget(f"{row.symbol}:{_interval}"):
                    continue
                await PlotKdjHandle(row.symbol, _interval).check_cross()

        time.sleep(110)


if __name__ == "__main__":
    main()
