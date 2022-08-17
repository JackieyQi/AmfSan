#! /usr/bin/env python
# coding:utf8

import os
import json


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    with open("{}/settings/cfg.json".format(BASE_DIR)) as f:
        cfgs = json.loads(f.read())
except BaseException as e:
    print(e)

try:
    with open("{}/settings/cfg_pro.json".format(BASE_DIR)) as f:
        cfgs = json.loads(f.read())
except BaseException as e:
    print(e)

try:
    with open("{}/settings/cfg_huobi.json".format(BASE_DIR)) as f:
        cfgs_huobi = json.loads(f.read())
except BaseException as e:
    print(e)
    cfgs_huobi = None
