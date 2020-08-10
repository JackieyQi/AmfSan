#! /usr/bin/env python
# coding:utf8

import redis
from kombu import Queue, Exchange, Connection

from settings.setting import cfgs


redis_client = redis.Redis(
    connection_pool=redis.ConnectionPool(
        host=cfgs["redis"]["host"], port=cfgs["redis"]["port"], db=cfgs["redis"]["db"], decode_responses=True
    )
)
try:
    redis_client.get("test")
except BaseException as e:
    print("Error: Cant connect to redis, {}".format(e))


amf_exchange = Exchange(cfgs["rabbitmq"]["amf_exchange"], "direct", durable=True)
amf_queue = Queue("amf", exchange=amf_exchange, routing_key="amf")
queue_conn = Connection(
    "amqp://{}:{}@{}:{}/{}".format(cfgs["rabbitmq"]["user"], cfgs["rabbitmq"]["pwd"],
                                   cfgs["rabbitmq"]["host"], cfgs["rabbitmq"]["port"],
                                   cfgs["rabbitmq"]["vhost"])
)
try:
    queue_conn.connect()
    queue_conn.release()
except BaseException as e:
    print("Error: Cant connect rabbitmq, {}".format(e))

