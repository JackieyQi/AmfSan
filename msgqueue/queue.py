#! /usr/bin/env python
# coding:utf8

import time
import logging
import traceback
import ujson as json
from exts import queue_conn_manager, amf_msg_queue, amf_plot_queue, kombu_conn_manager, amf_kline_queue


logger = logging.getLogger("MQ")


async def push_msg(value):
    try:
        connection = queue_conn_manager.get_connection()
        with connection.SimpleQueue(amf_msg_queue) as q:
            q.put(json.dumps(value), timeout=5)
    except BaseException as e:
        logger.error("{}".format(traceback.format_exc()))
    return True


async def push_plotmq(value):
    value.update({"ts": int(time.time())})

    connection = queue_conn_manager.get_connection()
    with connection.SimpleQueue(amf_plot_queue) as q:
        q.put(json.dumps(value), timeout=5)


async def push_symbol_mq(value):
    connection = kombu_conn_manager.get_connection()
    with connection.SimpleQueue(amf_kline_queue) as q:
        q.put(json.dumps(value), timeout=5)

    kombu_conn_manager.release_connection(connection)
