#! /usr/bin/env python
# coding:utf8

import time
from business.market import MarketPriceHandler
from msgqueue.tasks.plot import PlotPriceHandle


def main():
    print("Start plot script: check_price_job")
    while 1:
        market_price_handler = MarketPriceHandler()
        for symbol, price in market_price_handler.get_all_limit_price().items():
            PlotPriceHandle(symbol, price).check_limit_price_unsync()

        time.sleep(30)


if __name__ == "__main__":
    main()
