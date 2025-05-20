#! /usr/bin/env python
# coding:utf8

import logging
import traceback

import ujson as json
from amf import app
from utils.common import ts2fmt

from .queue import push_msg
from .tasks import dw, plot, sms, cache_sync

logger = logging.getLogger(__name__)

route_map = {
    #
    "sync_cache_job": cache_sync.sync_cache_job,
    #
    "send_email_task": sms.send_email,
    #
    "save_kline_job": dw.save_kline_job,
    "save_indicators_job": dw.save_indicators_job,
    "save_indicators_job_by_symbol": dw.save_indicators_job_by_symbol,
    #
    "save_account_balance_job": dw.save_account_balance_job,
    "save_trade_history_job": dw.save_trade_history_job,
    "update_price_job": dw.update_price,
    "update_fng_job": dw.update_fng_job,
    #
    "check_balance_job": plot.check_balance,
    "check_price_job": plot.check_price,
    "check_break_history_top_price_job": plot.check_break_history_top_price,
    "check_strategy_job": plot.check_strategy,
    "check_strategy_by_symbol": plot.check_strategy_by_symbol,
    #
    "update_all_symbols_job": plot.update_all_symbols,
    "cleanup_inactive_symbols_job": plot.cleanup_inactive_symbols,
}


async def deal_msg(msg):
    logger.debug("tasks deal_msg, msg:{}".format(msg))
    msg = json.loads(msg)
    if not isinstance(msg, dict):
        return

    msg_bp = msg.pop("bp")
    if msg_bp not in route_map:
        logger.info("tasks deal_msg, msg bp not exist:{}".format(msg))
        return

    logger.debug(
        "tasks deal_msg, task:{}, start:{}, kwargs:{}".format(msg_bp, ts2fmt(), msg)
    )
    func = route_map[msg_bp]
    try:
        _ = await func(msg)
        logger.debug(
            "tasks deal_msg over, task:{}, start:{}, kwargs:{}".format(msg_bp, ts2fmt(), msg)
        )
    except BaseException:

        error = traceback.format_exc()
        logger.error("tasks route exception, msg bp:{}, exc:{}".format(msg_bp, error))
        err_info = msg.copy()
        err_info["bp"] = "_function_call"
        err_info["function_module"] = "{}".format(func.__module__)
        err_info["function_name"] = "{}".format(func.__name__)

        _ = await push_msg(
            {
                "bp": "send_email_task",
                "title": msg_bp,
                "receiver": app.config.administrator_email,
                "content": "{}<br/><br/><br/>{}".format(error, json.dumps(err_info)),
            }
        )
        return
    logger.debug(
        "tasks deal_msg, task:{}, end:{}, kwargs:{}".format(msg_bp, ts2fmt(), msg)
    )
