#! /usr/bin/env python
# coding:utf8

import logging
import traceback
import ssl
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formatdate
from cache import AllCache

from settings.setting import cfgs


logger = logging.getLogger(__name__)


def check_email_send_limit():
    redis_client = AllCache.get_client()
    redis_key = "email_send_limit"
    count = redis_client.get(redis_key)
    if count and int(count) >= 100:
        return True
    
    if count is None:
        redis_client.set(redis_key, 1, ex=600)
    else:
        redis_client.incr(redis_key)
    redis_client.close()
    return False


def send_email(recipient, subject, text, from_name="AMF"):
    if check_email_send_limit():
        return

    if isinstance(recipient, list):
        # msg["To"] = ";".join(recipient)
        for _recipient in recipient:
            _send_email(_recipient, subject, text, from_name)
    else:
        _send_email(recipient, subject, text, from_name)


def _send_email(recipient, subject, text, from_name):
    msg = MIMEMultipart()
    msg["To"] = recipient
    msg["Subject"] = Header(subject, "utf-8")
    msg["Accept-Language"] = "zh-CN"
    msg["Accept-Charset"] = "ISO-8859-1,utf-8"
    msg["Date"] = formatdate(localtime=True)

    msg_body = MIMEText(text, "html", "utf-8")
    msg_body.set_charset("utf-8")
    msg.attach(msg_body)

    account = cfgs["email_sender"]
    context = ssl.SSLContext(ssl.PROTOCOL_TLS)
    msg["From"] = "{} <{}>".format(Header(from_name, "utf-8"), account["user"])
    try:
        with smtplib.SMTP_SSL(account["smtp"], account["port"]) as server:
            server.login(account["user"], account["pwd"])
            server.sendmail(account["user"], recipient, msg.as_string())

        # mail_server = smtplib.SMTP("{}:{}".format(account["smtp"], account["port"]), timeout=15)
        # mail_server.ehlo()
        # mail_server.starttls(context=context)
        # mail_server.ehlo()
        # mail_server.login(account["user"], account["pwd"])
        # mail_server.sendmail(account["user"], recipient, msg.as_string())
        # mail_server.quit()
        logger.info("Email send success")
        return True
    except BaseException as e:
        logger.error(",".join((str(e), traceback.format_exc())))
