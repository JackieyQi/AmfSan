#! /usr/bin/env python
# coding:utf8

import asyncio
import logging
import sys

from exts import amf_queue, queue_conn, amf_queue_plot
from msgqueue import deal_msg

logger = logging.getLogger("amfconsumer")

RESTART = False
RESTART_PLOT = False


async def consumer():
    queue_conn.connect()
    mq = queue_conn.SimpleQueue(amf_queue)

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
            mq = queue_conn.SimpleQueue(amf_queue)

        if not value:
            await asyncio.sleep(0.5)
            continue
        # print(value)
        # print(type(value), value.body)
        await deal_msg(value.body)

    mq_plot = queue_conn.SimpleQueue(amf_queue_plot)
    global RESTART_PLOT
    while 1:
        if RESTART_PLOT:
            logger.info("Consumer will quit")
            sys.exit(0)

        value = None
        try:
            value = mq_plot.get(block=False, timeout=1)
            value.ack()
        except mq_plot.Empty:
            pass
        except:
            queue_conn.connect()
            mq_plot = queue_conn.SimpleQueue(amf_queue_plot)

        if not value:
            await asyncio.sleep(0.5)
            continue
        await deal_msg(value.body)


def deal_signal(*args, **kwargs):
    global RESTART
    RESTART = True

    global RESTART_PLOT
    RESTART = True
    logger.info("Consumer restart")
