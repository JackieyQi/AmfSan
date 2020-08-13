#! /usr/bin/env python
# coding:utf8

from exts import redis_client


r_client = None

class Base(object):
    @staticmethod
    def redis():
        global r_client
        if not r_client:
            r_client = redis_client
        return r_client


class StringCache(Base):
    @classmethod
    def get(cls):
        return cls.redis().get(cls.key)

    @classmethod
    def set(cls, val, ex=180):
        return cls.redis().set(cls.key, val, ex)


class HashCache(Base):
    @classmethod
    def hgetall(cls):
        return cls.redis().hgetall(cls.key)

    @classmethod
    def hget(cls, key):
        return cls.redis().hget(cls.key, key)

    @classmethod
    def hset(cls, key, val):
        return cls.redis().hset(cls.key, key, val)

    @classmethod
    def hmget(cls, map_keys):
        return cls.redis().hmget(cls.key, map_keys)

    @classmethod
    def hmset(cls, map_vals):
        return cls.redis().hmset(cls.key, map_vals)

