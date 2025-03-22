#! /usr/bin/env python
# coding:utf8

import redis
import threading
import logging.config
from kombu import Connection, Exchange, Queue
from playhouse.pool import PooledMySQLDatabase
from peewee_async import PooledMySQLDatabase as AsyncPooledMySQLDatabase

from settings import log
from settings.setting import cfgs


debug = cfgs["debug"]
mycnf = cfgs["mysql"]


class RedisClient:
    _connection_pool = None

    @classmethod
    def get_connection_pool(cls):
        if cls._connection_pool is None:
            cls._connection_pool = redis.ConnectionPool(
                host=cfgs["redis"]["host"],
                port=cfgs["redis"]["port"],
                db=cfgs["redis"]["db"],
                decode_responses=True,
            )
        return cls._connection_pool


class MysqlClient:
    _database = None

    @classmethod
    def get_database(cls):
        if cls._database and not cls._database.is_closed():
            return cls._database

        try:
            cls._database = PooledMySQLDatabase(
                mycnf["db"],
                host=mycnf["host"],
                port=mycnf["port"],
                charset=mycnf["charset"],
                user=mycnf["user"],
                passwd=mycnf["pwd"],
                max_connections=mycnf["connections"],
                stale_timeout=mycnf["timeout"],
                timeout=30,
            )
            cls._database.connect(reuse_if_open=True)  # 显式建立连接
        except BaseException as e:
            print(f"数据库连接失败: {e}")
            cls._database = None  # 避免使用错误的连接
        return cls._database


try:
    async_database = AsyncPooledMySQLDatabase(
        mycnf["db"],
        host=mycnf["host"],
        port=mycnf["port"],
        charset=mycnf["charset"],
        user=mycnf["user"],
        password=mycnf["pwd"],
        max_connections=mycnf["connections"],
        connect_timeout=mycnf["timeout"],
    )
except BaseException as e:
    print(f"数据库连接失败: {e}")


amf_exchange = Exchange(cfgs["rabbitmq"]["amf_exchange"], "direct", durable=True)
amf_queue = Queue("amf", exchange=amf_exchange, routing_key="amf")
amf_kline_queue = Queue("amf_kline", exchange=amf_exchange, routing_key="amf_kline")
amf_plot_queue = Queue("amf_plot", exchange=amf_exchange, routing_key="amf_plot")
amf_msg_queue = Queue("amf_msg", exchange=amf_exchange, routing_key="amf_msg")


class QueueLongConnectionManager(object):
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


class QueueKombuConnectionManager(object):
    def __init__(self, url, pool_size=10):
        self.url = url
        self.pool_size = pool_size
        self.connections = []
        self.lock = threading.Lock()
        self.initialize()

    def initialize(self):
        with self.lock:
            for _ in range(self.pool_size):
                connection = Connection(self.url)
                self.connections.append(connection)

    def get_connection(self):
        with self.lock:
            if not self.connections:
                return Connection(self.url)
            return self.connections.pop()

    def release_connection(self, connection):
        with self.lock:
            if len(self.connections) < self.pool_size:
                self.connections.append(connection)
            else:
                connection.release()

    def close(self):
        with self.lock:
            for connection in self.connections:
                connection.release()
            self.connections.clear()


queue_conn_manager = QueueLongConnectionManager(
    "amqp://{}:{}@{}:{}/{}".format(
        cfgs["rabbitmq"]["user"],
        cfgs["rabbitmq"]["pwd"],
        cfgs["rabbitmq"]["host"],
        cfgs["rabbitmq"]["port"],
        cfgs["rabbitmq"]["vhost"],
    )
)


kombu_conn_manager = QueueKombuConnectionManager(
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
