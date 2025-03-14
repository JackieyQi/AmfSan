#! /usr/bin/env python
# coding:utf8

import redis
from exts import RedisClient


class RedisPoolContext(object):
    def __init__(self):
        self.pool = RedisClient.get_connection_pool()

    def __enter__(self):
        self.redis = redis.Redis(connection_pool=self.pool)
        return self.redis

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.redis:
            self.redis.close()


class Base(object):
    key = "Base"


class AllCache(Base):
    @classmethod
    def get_client(cls):
        pool = RedisClient.get_connection_pool()
        return redis.Redis(connection_pool=pool)

    @classmethod
    def get_all(cls):
        client = cls.get_client()
        try:
            return client.keys()
        except redis.exceptions.ConnectionError as e:
            print(f"Error: Redis connection error, {e}")
            return None
        finally:
            client.close()

    @classmethod
    def get_type(cls, val):
        client = cls.get_client()
        try:
            return client.type(val)
        except redis.exceptions.ConnectionError as e:
            print(f"Error: Redis connection error, {e}")
            return None
        finally:
            client.close()


class StringCache(AllCache):
    @classmethod
    def get(cls):
        return cls.get_client().get(cls.key)

    @classmethod
    def set(cls, val, ex=180):
        return cls.get_client().set(cls.key, val, ex)

    @classmethod
    def incr(cls):
        return cls.get_client().incr(cls.key)

    @classmethod
    def delete(cls):
        return cls.get_client().delete(cls.key)


class ListCache(AllCache):
    @classmethod
    def rpush(cls, val):
        return cls.get_client().rpush(cls.key, val)

    @classmethod
    def rpop(cls):
        return cls.get_client().rpop(cls.key)

    @classmethod
    def llen(cls):
        return cls.get_client().llen(cls.key)

    @classmethod
    def delete(cls):
        return cls.get_client().delete(cls.key)


class HashCache(AllCache):
    @classmethod
    def hgetall(cls):
        return cls.get_client().hgetall(cls.key)

    @classmethod
    def hget(cls, key):
        return cls.get_client().hget(cls.key, key)

    @classmethod
    def hset(cls, key, val):
        return cls.get_client().hset(cls.key, key, val)

    @classmethod
    def hdel(cls, key):
        return cls.get_client().hdel(cls.key, key)

    @classmethod
    def hmget(cls, map_keys):
        return cls.get_client().hmget(cls.key, map_keys)

    @classmethod
    def hmset(cls, map_vals):
        return cls.get_client().hmset(cls.key, map_vals)

    @classmethod
    def delete(cls):
        return cls.get_client().delete(cls.key)
