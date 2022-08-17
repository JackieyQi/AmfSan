#! /usr/bin/env python
# coding:utf8

from exts import database
from peewee import Model


class Base(Model):
    class Meta:
        database = database
        only_save_dirty = True
