#! /usr/bin/env python
# coding:utf8

import redis
import logging.config
from kombu import Connection, Exchange, Queue
from playhouse.pool import PooledMySQLDatabase

from settings import log
from settings.setting import cfgs


debug = cfgs["debug"]


redis_client = redis.Redis(
    connection_pool=redis.ConnectionPool(
        host=cfgs["redis"]["host"],
        port=cfgs["redis"]["port"],
        db=cfgs["redis"]["db"],
        decode_responses=True,
    )
)
try:
    redis_client.get("test")
except BaseException as e:
    print("Error: Cant connect to redis, {}".format(e))


"""
Initialize Database:
from exts import database
from models import Table
# database.connect()
database.create_tables([Table, ])

"""
mycnf = cfgs["mysql"]
database = PooledMySQLDatabase(
    mycnf["db"],
    host=mycnf["host"],
    port=mycnf["port"],
    charset=mycnf["charset"],
    user=mycnf["user"],
    passwd=mycnf["pwd"],
    max_connections=mycnf["connections"],
    stale_timeout=mycnf["timeout"],
)


amf_exchange = Exchange(cfgs["rabbitmq"]["amf_exchange"], "direct", durable=True)
amf_queue = Queue("amf", exchange=amf_exchange, routing_key="amf")
amf_msg_queue = Queue("amf_msg", exchange=amf_exchange, routing_key="amf_msg")

queue_conn = Connection(
    "amqp://{}:{}@{}:{}/{}".format(
        cfgs["rabbitmq"]["user"],
        cfgs["rabbitmq"]["pwd"],
        cfgs["rabbitmq"]["host"],
        cfgs["rabbitmq"]["port"],
        cfgs["rabbitmq"]["vhost"],
    )
)
try:
    queue_conn.connect()
    queue_conn.release()
except BaseException as e:
    print("Error: Cant connect rabbitmq, {}".format(e))


if not debug:
    log.LOG_CONF["handlers"]["console"]["level"] = "WARNING"
logging.config.dictConfig(log.LOG_CONF)
