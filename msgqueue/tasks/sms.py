#! /usr/bin/env python
# coding:utf8

import logging
from business import mail_serve

logger = logging.getLogger(__name__)


async def send_email(value: dict):
    logger.info(f"send_email, value:{value}")
    mail_serve.send_email(
        value.get("receiver", ""), value.get("title", ""), value.get("content", "")
    )
