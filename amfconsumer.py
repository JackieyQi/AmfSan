#! /usr/bin/env python
# coding:utf8

import asyncio
import logging
import sys

from exts import amf_queue, queue_conn
from msgqueue import deal_msg

logger = logging.getLogger("amfconsumer")

RESTART = False


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
        print(value)
        print(type(value), value.body)
        await deal_msg(value.body)


def deal_signal(*args, **kwargs):
    global RESTART
    RESTART = True
    logger.info("Consumer restart")
