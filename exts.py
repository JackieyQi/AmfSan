#! /usr/bin/env python
# coding:utf8

import redis
import threading
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
amf_kline_queue = Queue("amf_kline", exchange=amf_exchange, routing_key="amf_kline")
amf_plot_queue = Queue("amf_plot", exchange=amf_exchange, routing_key="amf_plot")
amf_msg_queue = Queue("amf_msg", exchange=amf_exchange, routing_key="amf_msg")

amf_tmp1_queue = Queue("amf_tmp1_msg", exchange=amf_exchange, routing_key="amf_tmp1_msg")
amf_tmp2_queue = Queue("amf_tmp2_msg", exchange=amf_exchange, routing_key="amf_tmp2_msg")


class QueueConnectionManager(object):
    def __init__(self, url):
        self.url = url
        self.connection = None
        self.lock = threading.Lock()
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5

    def get_connection(self):
        with self.lock:
            if self.connection is None or not self.connection.connected:
                self.connect()
            return self.connection

    def connect(self):
        try:
            self.connection = Connection(self.url)
            self.connection.connect()
            self.reconnect_attempts = 0 # 重置重连计数
            print("Successfully connected to RabbitMQ")
        except Exception as e:
            self.reconnect_attempts += 1
            print(f"Failed to connect to RabbitMQ: {str(e)}")
            if self.reconnect_attempts >= self.max_reconnect_attempts:
                print("Max reconnection attempts reached!")
            raise


queue_conn_manager = QueueConnectionManager(
    "amqp://{}:{}@{}:{}/{}".format(
        cfgs["rabbitmq"]["user"],
        cfgs["rabbitmq"]["pwd"],
        cfgs["rabbitmq"]["host"],
        cfgs["rabbitmq"]["port"],
        cfgs["rabbitmq"]["vhost"],
    )
)


if not debug:
    log.LOG_CONF["handlers"]["console"]["level"] = "WARNING"
logging.config.dictConfig(log.LOG_CONF)
