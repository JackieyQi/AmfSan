#! /usr/bin/env python
# coding:utf8

import redis
from kombu import Queue, Exchange, Connection

from amf import app


redis_client = redis.Redis(
    connection_pool=redis.ConnectionPool(
        host=app.config.redis["host"], port=app.config.redis["port"], db=app.config.redis["db"], decode_responses=True
    )
)
try:
    redis_client.get("test")
except BaseException as e:
    print("Error: Cant connect to redis, {}".format(e))


amf_exchange = Exchange(app.config.rabbitmq["amf_exchange"], "direct", durable=True)
amf_queue = Queue("amf", exchange=amf_exchange, routing_key="amf")
queue_conn = Connection(
    "amqp://{}:{}@{}:{}/{}".format(app.config.rabbitmq["user"], app.config.rabbitmq["pwd"],
                                   app.config.rabbitmq["host"], app.config.rabbitmq["port"],
                                   app.config.rabbitmq["vhost"])
)
try:
    queue_conn.connect()
    queue_conn.release()
except BaseException as e:
    print("Error: Cant connect rabbitmq, {}".format(e))

