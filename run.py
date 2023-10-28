#! /usr/bin/env python
# coding:utf8

from amf import app

# Low level running sanic
if __name__ == "__main__":
    app.run(host=app.config.host, port=app.config.port, debug=app.config.debug, access_log=False)
