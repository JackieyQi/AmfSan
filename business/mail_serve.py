#! /usr/bin/env python
# coding:utf8

import logging
import traceback
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formatdate

from amf import app


logger = logging.getLogger(__name__)

def send_email(recipient, subject, text, from_name="AMF"):
    
    msg = MIMEMultipart()
    if isinstance(recipient, list):
        msg["To"] = ";".join(recipient)
    else:
        msg["To"] = recipient
    msg["Subject"] = Header(subject, "utf-8")
    msg["Accept-Language"] = "zh-CN"
    msg["Accept-Charset"] = "ISO-8859-1,utf-8"
    msg["Date"] = formatdate(localtime=True)

    msg_body = MIMEText(text, "html", "utf-8")
    msg_body.set_charset("utf-8")
    msg.attach(msg_body)

    accounts = [{
        "username": app.config.email["sys_name"],
        "password": app.config.email["sys_pwd"],
        "smtp": "smtp.gmail.com",
        "port": 465
    }, ]

    for i in accounts:
        msg["From"] = "{} <{}>".format(Header(from_name, "utf-8"), i["username"])
        try:
            mail_server = smtplib.SMTP_SSL("{}:{}".format(i["smtp"], a["port"]), timeout=15)
            mail_server.login(i["username"], i["password"])
            mail_server.sendmail(i["username"], recipient, msg.as_string())
            mail_server.quit()
            logger.info("Email send success")
            return True
        except BaseException as e:
            logger.error(",".join((e, traceback.format_exc())))

