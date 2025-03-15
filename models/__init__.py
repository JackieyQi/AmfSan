#! /usr/bin/env python
# coding:utf8

import peewee
from exts import MysqlClient, database


class Base(peewee.Model):
    class Meta:
        # database = MysqlClient.get_database()
        database = database
        only_save_dirty = True
