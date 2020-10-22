#! /usr/bin/env python
# coding:utf8

import time
import logging
import schedule
import ujson as json

from settings.setting import cfgs
from exts import amf_queue, queue_conn


logger = logging.getLogger(__name__)

def push2mq(bp, **kwargs):
    kwargs.update({"bp": bp, "ts": int(time.time())})

    queue_conn.connect()
    with queue_conn.SimpleQueue(amf_queue) as q:
        q.put(json.dumps(kwargs))
        logger.info("Scheduler start job:{}, kwargs:{}".format(bp, kwargs))
    queue_conn.release()


def check_price_job():
    push2mq("check_price_job")


def save_account_balance_job():
    push2mq("save_account_balance_job")


def schedules():
    schedule.every(30).seconds.do(check_price_job)
    schedule.every().day.at("02:00").do(save_account_balance_job)
    schedule.every().day.at("14:00").do(save_account_balance_job)

    while True:
        schedule.run_pending()
        time.sleep(0.2)

