#! /usr/bin/env python
# coding:utf8

from peewee import Model

from exts import database 


class Base(Model):
    class Meta:
        database = database
        only_save_dirty = True

