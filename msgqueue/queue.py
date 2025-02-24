#! /usr/bin/env python
# coding:utf8

import time
import logging
import traceback
import ujson as json
from exts import queue_conn, amf_msg_queue, amf_plot_queue


logger = logging.getLogger("MQ")


async def push_msg(value):
    try:
        with queue_conn.SimpleQueue(amf_msg_queue) as queue:
            queue.put(json.dumps(value))
    except BaseException as e:
        logger.error("{}".format(traceback.format_exc()))
    return True


async def push_plotmq(value):
    value.update({"ts": int(time.time())})

    # queue_conn.connect()
    with queue_conn.SimpleQueue(amf_plot_queue) as q:
        q.put(json.dumps(value))
    # queue_conn.release()
