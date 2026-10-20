#! /usr/bin/env python
# coding:utf8

import logging
from business import mail_serve

logger = logging.getLogger(__name__)


async def send_email(value: dict):
    if "monitor_id" in value:
        from business.monitor import deliver_monitor_notice
        return await deliver_monitor_notice(value)
    # Queued notices from the retired automatic/independent-price flow have no owner/version.
    if value.get("title", "").endswith((" Strategy Check Notice", " Price Notice")):
        logger.info("discard retired monitor notice")
        return
    # logger.info(f"send_email, value:{value}")
    mail_serve.send_email(
        value.get("receiver", ""), value.get("title", ""), value.get("content", "")
    )
