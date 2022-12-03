#! /usr/bin/env python
# coding:utf8

from amf import app

app.run(host=app.config.host, port=app.config.port, debug=app.config.debug)
