#! /usr/bin/env python
# coding:utf8

from exts import MysqlClient
from peewee import Model


class Base(Model):
    class Meta:
        database = MysqlClient.get_database()
        only_save_dirty = True
