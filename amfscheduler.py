#! /usr/bin/env python
# coding:utf8

import logging
import time

import schedule
import ujson as json

from exts import amf_queue, queue_conn

logger = logging.getLogger(__name__)


def push2mq(bp, **kwargs):
    kwargs.update({"bp": bp, "ts": int(time.time())})

    queue_conn.connect()
    with queue_conn.SimpleQueue(amf_queue) as q:
        q.put(json.dumps(kwargs))
        logger.info("Scheduler start job:{}, kwargs:{}".format(bp, kwargs))
    queue_conn.release()


def sync_cache_job():
    push2mq("sync_cache_job")


def check_price_job():
    push2mq("check_price_job")


def check_macd_cross_job():
    push2mq("check_macd_cross_job")


def check_macd_trend_job():
    push2mq("check_macd_trend_job")


def check_balance_job():
    push2mq("check_balance_job")


def save_macd_job():
    push2mq("save_macd_job")


def save_account_balance_job():
    push2mq("save_account_balance_job")


def save_trade_history_job():
    push2mq("save_trade_history_job")


def schedules():
    schedule.every(17).seconds.do(sync_cache_job)

    schedule.every(30).seconds.do(check_price_job)

    schedule.every(3).minutes.do(save_macd_job)

    schedule.every(13).minutes.do(check_macd_cross_job)
    # schedule.every(13).minutes.do(check_macd_trend_job)

    # user action
    # schedule.every().day.at("05:00").do(save_trade_history_job)
    # schedule.every().day.at("15:27").do(check_balance_job)
    # schedule.every().day.at("03:17").do(save_account_balance_job)
    # schedule.every().day.at("15:17").do(save_account_balance_job)

    while True:
        schedule.run_pending()
        time.sleep(0.2)
