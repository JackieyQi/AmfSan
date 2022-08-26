#! /usr/bin/env python
# coding:utf8

import logging
import traceback

import ujson as json
from amf import app
from utils.common import ts2fmt

from .queue import push
from .tasks import account, market, sms

logger = logging.getLogger(__name__)

route_map = {
    "send_email_task": sms.send_email,
    "check_price_job": market.check_price,
    "check_macd_job": market.check_macd,
    "save_account_balance_job": account.save_account_balance_job,
    "update_trade_history_job": account.update_trade_history_job,
}


async def deal_msg(msg):
    logger.info("tasks deal_msg, msg:{}".format(msg))
    msg = json.loads(msg)
    if not isinstance(msg, dict):
        return

    msg_bp = msg.pop("bp")
    if msg_bp not in route_map:
        logger.info("tasks deal_msg, msg bp not exist:{}".format(msg))
        return

    logger.info(
        "tasks deal_msg, task:{}, start:{}, kwargs:{}".format(msg_bp, ts2fmt(), msg)
    )
    func = route_map[msg_bp]
    try:
        _ = await func(msg)
    except BaseException:

        error = traceback.format_exc()
        logger.error("tasks route exception, msg bp:{}, exc:{}".format(msg_bp, error))
        err_info = msg.copy()
        err_info["bp"] = "_function_call"
        err_info["function_module"] = "{}".format(func.__module__)
        err_info["function_name"] = "{}".format(func.__name__)

        _ = await push(
            {
                "bp": "send_email",
                "title": msg_bp,
                "receiver": app.config.administrator_email,
                "content": "{}<br/><br/><br/>{}".format(error, json.dumps(err_info)),
            }
        )
        return
    logger.info(
        "tasks deal_msg, task:{}, end:{}, kwargs:{}".format(msg_bp, ts2fmt(), msg)
    )
