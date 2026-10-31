#! /usr/bin/env python
# coding:utf8

import logging
import os
import traceback
import ssl
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formatdate
from urllib.parse import unquote, urlsplit
from cache import check_rate_limit

from settings.setting import cfgs


logger = logging.getLogger(__name__)


class _ProxySMTPSSL(smtplib.SMTP_SSL):
    """Use a per-connection SOCKS socket without changing global networking."""

    def __init__(self, host, port, proxy_url, timeout=15):
        try:
            proxy = urlsplit(proxy_url)
            if proxy.scheme not in ("socks5", "socks5h") or not proxy.hostname:
                raise ValueError
            self._proxy_host = proxy.hostname
            self._proxy_port = proxy.port or 1080
            self._proxy_rdns = proxy.scheme == "socks5h"
            self._proxy_user = unquote(proxy.username) if proxy.username else None
            self._proxy_password = unquote(proxy.password) if proxy.password else None
        except ValueError:
            raise ValueError("ALL_PROXY must be a valid socks5:// or socks5h:// URL") from None
        super().__init__(host, port, timeout=timeout, context=ssl.create_default_context())

    def _get_socket(self, host, port, timeout):
        import socks

        sock = socks.create_connection(
            (host, port), timeout=timeout,
            proxy_type=socks.SOCKS5,
            proxy_addr=self._proxy_host, proxy_port=self._proxy_port,
            proxy_rdns=self._proxy_rdns,
            proxy_username=self._proxy_user, proxy_password=self._proxy_password,
        )
        try:
            return self.context.wrap_socket(sock, server_hostname=host)
        except BaseException:
            sock.close()
            raise


def _smtp_connection(account):
    proxy_url = (os.getenv("ALL_PROXY") or os.getenv("all_proxy") or "").strip()
    if proxy_url:
        logger.info("Email SMTP connection using SOCKS5 proxy")
        return _ProxySMTPSSL(account["smtp"], account["port"], proxy_url)
    return smtplib.SMTP_SSL(account["smtp"], account["port"], timeout=15)


def send_email(recipient, subject, text, from_name="AMF"):
    if check_rate_limit("email_send_limit", limit=100, expire=600):
        recipient_count = len(recipient) if isinstance(recipient, list) else 1
        logger.warning(
            "Email send skipped by rate limit, subject:%s, recipient_count:%s",
            subject,
            recipient_count,
        )
        return

    if isinstance(recipient, list):
        # msg["To"] = ";".join(recipient)
        results = [_send_email(item, subject, text, from_name) for item in recipient]
        return bool(results) and all(results)
    else:
        return _send_email(recipient, subject, text, from_name)


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
    msg["From"] = "{} <{}>".format(Header(from_name, "utf-8"), account["user"])
    try:
        with _smtp_connection(account) as server:
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
        logger.error(
            "Email send failed, subject:%s, recipient_count:%s, error:%s,%s",
            subject,
            1,
            str(e),
            traceback.format_exc(),
        )
