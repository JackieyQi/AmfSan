#! /usr/bin/env python
# coding:utf8

import peewee_async
from exts import MysqlClient, async_database


class Base(peewee_async.AioModel):
    class Meta:
        # database = MysqlClient.get_database()
        database = async_database
        only_save_dirty = True
