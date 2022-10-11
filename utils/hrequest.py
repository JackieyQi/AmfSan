#! /usr/bin/env python
# coding:utf8

import json
from urllib.parse import urlencode, urlparse

import requests


def http_get_request(url, payload, add_headers=None):
    headers = {
        "Content-type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.71 Safari/537.36",
    }
    if add_headers:
        headers.update(add_headers)

    try:
        resp = requests.get(url, urlencode(payload), headers=headers, timeout=15)
        if resp.status_code == 200:
            return resp.json()
    except BaseException as e:
        # logger.error(e)
        pass
    return


def http_post_request(url, payload, add_headers=None):
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if add_headers:
        headers.update(add_headers)

    try:
        resp = requests.post(url, json.dumps(payload), headers=headers, timeout=15)
        if resp.status_code == 200:
            return resp.json()
    except BaseException as e:
        # logger.error(e)
        pass
    return
