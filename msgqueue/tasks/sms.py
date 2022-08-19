#! /usr/bin/env python
# coding:utf8

from business import mail_serve


async def send_email(value: dict):
    mail_serve.send_email(
        value.get("receiver", ""), value.get("title", ""), value.get("content", "")
    )
