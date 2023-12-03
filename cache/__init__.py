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

    @classmethod
    def incr(cls):
        return cls.redis().incr(cls.key)

    @classmethod
    def delete(cls):
        return cls.redis().delete(cls.key)


class ListCache(Base):
    @classmethod
    def rpush(cls, val):
        return cls.redis().rpush(cls.key, val)

    @classmethod
    def rpop(cls):
        return cls.redis().rpop(cls.key)

    @classmethod
    def llen(cls):
        return cls.redis().llen(cls.key)

    @classmethod
    def delete(cls):
        return cls.redis().delete(cls.key)


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
    def hdel(cls, key):
        return cls.redis().hdel(cls.key, key)

    @classmethod
    def hmget(cls, map_keys):
        return cls.redis().hmget(cls.key, map_keys)

    @classmethod
    def hmset(cls, map_vals):
        return cls.redis().hmset(cls.key, map_vals)

    @classmethod
    def delete(cls):
        return cls.redis().delete(cls.key)
