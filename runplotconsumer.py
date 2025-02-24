#! /usr/bin/env python
# coding:utf8

import asyncio
import signal
import uvloop
import logging
import sys

from exts import amf_plot_queue, queue_conn
from msgqueue import deal_msg

logger = logging.getLogger(__name__)

RESTART = False


async def consumer():
    queue_conn.connect()
    mq = queue_conn.SimpleQueue(amf_plot_queue)

    global RESTART
    while 1:
        if RESTART:
            logger.info("Consumer will quit")
            sys.exit(0)

        value = None
        try:
            value = mq.get(block=False, timeout=1)
            value.ack()
        except mq.Empty:
            pass
        except:
            queue_conn.connect()
            mq = queue_conn.SimpleQueue(amf_plot_queue)

        if not value:
            await asyncio.sleep(0.5)
            continue

        await deal_msg(value.body)


def deal_signal(*args, **kwargs):
    global RESTART
    RESTART = True

    logger.info("Consumer restart")


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
