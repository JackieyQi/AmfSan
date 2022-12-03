#! /usr/bin/env python
# coding:utf8

import asyncio
import signal
import uvloop

from amfconsumer import logger, deal_signal, consumer


def main():
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    print("Consumer start.")
    logger.info("Consumer start.")

    signal.signal(signal.SIGINT, deal_signal)
    signal.signal(signal.SIGUSR2, deal_signal)
    signal.signal(signal.SIGTERM, deal_signal)
    signal.signal(signal.SIGQUIT, deal_signal)
    signal.signal(signal.SIGHUP, deal_signal)

    _loop = asyncio.get_event_loop()
    _loop.run_until_complete(consumer())
    _loop.close()


if __name__ == "__main__":
    main()
