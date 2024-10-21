#! /usr/bin/env python
# coding:utf8

import logging
import traceback
import ujson as json
from exts import queue_conn, amf_queue


logger = logging.getLogger("MQ")


async def push(value):
    try:
        with queue_conn.SimpleQueue(amf_queue) as queue:
            queue.put(json.dumps(value))
    except BaseException as e:
        logger.error("{}".format(traceback.format_exc()))
    return True
