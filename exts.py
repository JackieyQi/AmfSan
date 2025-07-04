#! /usr/bin/env python
# coding:utf8

import redis
import threading
import logging.config
import time
from contextlib import asynccontextmanager, contextmanager
from typing import Optional, AsyncGenerator, Generator
from kombu import Connection, Exchange, Queue
from playhouse.pool import PooledMySQLDatabase
from peewee_async import PooledMySQLDatabase as AsyncPooledMySQLDatabase

from settings import log
from settings.setting import cfgs

logger = logging.getLogger(__name__)

debug = cfgs["debug"]
mycnf = cfgs["mysql"]


class RedisClient:
    _connection_pool = None
    _lock = threading.Lock()

    @classmethod
    def get_connection_pool(cls):
        if cls._connection_pool is None:
            with cls._lock:
                if cls._connection_pool is None:
                    cls._connection_pool = redis.ConnectionPool(
                        host=cfgs["redis"]["host"],
                        port=cfgs["redis"]["port"],
                        db=cfgs["redis"]["db"],
                        decode_responses=True,
                        max_connections=20,  # 设置最大连接数
                        retry_on_timeout=True,
                        socket_connect_timeout=5,
                        socket_timeout=5,
                    )
        return cls._connection_pool

    @classmethod
    def get_client(cls) -> redis.Redis:
        """获取Redis客户端实例"""
        return redis.Redis(connection_pool=cls.get_connection_pool())


class DatabaseConnectionManager:
    """数据库连接管理器 - 统一管理同步和异步连接"""
    
    _sync_database: Optional[PooledMySQLDatabase] = None
    _async_database: Optional[AsyncPooledMySQLDatabase] = None
    _lock = threading.Lock()
    _last_health_check = 0
    _health_check_interval = 300  # 5分钟检查一次

    @classmethod
    def _create_sync_database(cls) -> PooledMySQLDatabase:
        """创建同步数据库连接"""
        try:
            database = PooledMySQLDatabase(
                mycnf["db"],
                host=mycnf["host"],
                port=mycnf["port"],
                charset=mycnf["charset"],
                user=mycnf["user"],
                passwd=mycnf["pwd"],
                max_connections=min(mycnf["connections"], 20),  # 限制同步连接数
                stale_timeout=mycnf["timeout"],
                timeout=30,
                # 连接池优化参数
                autoconnect=True,
                autorollback=True,
            )
            
            # 测试连接
            database.connect(reuse_if_open=True)
            database.execute_sql('SELECT 1')
            logger.info("同步数据库连接建立成功")
            return database
            
        except Exception as e:
            logger.error(f"同步数据库连接失败: {e}")
            raise

    @classmethod
    def _create_async_database(cls) -> AsyncPooledMySQLDatabase:
        """创建异步数据库连接"""
        try:
            database = AsyncPooledMySQLDatabase(
                mycnf["db"],
                host=mycnf["host"],
                port=mycnf["port"],
                charset=mycnf["charset"],
                user=mycnf["user"],
                password=mycnf["pwd"],
                max_connections=mycnf["connections"],
                connect_timeout=mycnf["timeout"],
                # 异步连接池优化参数
                autoconnect=True,
                autorollback=True,
            )
            logger.info("异步数据库连接配置完成")
            return database
            
        except Exception as e:
            logger.error(f"异步数据库连接配置失败: {e}")
            raise

    @classmethod
    def get_sync_database(cls) -> PooledMySQLDatabase:
        """获取同步数据库连接（线程安全）"""
        if cls._sync_database is None or cls._sync_database.is_closed():
            with cls._lock:
                if cls._sync_database is None or cls._sync_database.is_closed():
                    cls._sync_database = cls._create_sync_database()
        
        # 定期健康检查
        cls._health_check_sync()
        return cls._sync_database

    @classmethod
    def get_async_database(cls) -> AsyncPooledMySQLDatabase:
        """获取异步数据库连接"""
        if cls._async_database is None:
            with cls._lock:
                if cls._async_database is None:
                    cls._async_database = cls._create_async_database()
        
        return cls._async_database

    @classmethod
    def _health_check_sync(cls):
        """同步数据库健康检查"""
        current_time = time.time()
        if current_time - cls._last_health_check > cls._health_check_interval:
            try:
                if cls._sync_database and not cls._sync_database.is_closed():
                    cls._sync_database.execute_sql('SELECT 1')
                cls._last_health_check = current_time
            except Exception as e:
                logger.warning(f"数据库健康检查失败，重建连接: {e}")
                cls._sync_database = None

    @classmethod
    @contextmanager
    def sync_transaction(cls) -> Generator[PooledMySQLDatabase, None, None]:
        """同步数据库事务上下文管理器"""
        database = cls.get_sync_database()
        with database.atomic():
            try:
                yield database
            except Exception as e:
                logger.error(f"同步事务执行失败: {e}")
                raise

    @classmethod
    @asynccontextmanager
    async def async_transaction(cls) -> AsyncGenerator[AsyncPooledMySQLDatabase, None]:
        """异步数据库事务上下文管理器"""
        database = cls.get_async_database()
        async with database.aio_atomic():
            try:
                yield database
            except Exception as e:
                logger.error(f"异步事务执行失败: {e}")
                raise

    @classmethod
    def close_all_connections(cls):
        """关闭所有数据库连接"""
        with cls._lock:
            if cls._sync_database and not cls._sync_database.is_closed():
                cls._sync_database.close()
                logger.info("同步数据库连接已关闭")
            
            if cls._async_database:
                # 异步数据库连接的关闭需要在事件循环中进行
                logger.info("异步数据库连接标记为关闭")
                cls._async_database = None

    @classmethod
    def get_connection_status(cls) -> dict:
        """获取连接状态信息"""
        return {
            "sync_database_closed": cls._sync_database is None or cls._sync_database.is_closed(),
            "async_database_configured": cls._async_database is not None,
            "last_health_check": cls._last_health_check,
        }


# 为了保持向后兼容性，保留原有的类和实例
class MysqlClient:
    """保持向后兼容的同步数据库客户端"""
    
    @classmethod
    def get_database(cls) -> PooledMySQLDatabase:
        return DatabaseConnectionManager.get_sync_database()


# 全局实例
database_manager = DatabaseConnectionManager()
async_database = database_manager.get_async_database()

# 向后兼容
database = async_database


# RabbitMQ 相关（保持原有逻辑）
amf_exchange = Exchange(cfgs["rabbitmq"]["amf_exchange"], "direct", durable=True)
amf_queue = Queue("amf", exchange=amf_exchange, routing_key="amf")
amf_kline_queue = Queue("amf_kline", exchange=amf_exchange, routing_key="amf_kline")
amf_plot_queue = Queue("amf_plot", exchange=amf_exchange, routing_key="amf_plot")
amf_msg_queue = Queue("amf_msg", exchange=amf_exchange, routing_key="amf_msg")


class QueueConnectionManager:
    """优化的队列连接管理器"""
    
    def __init__(self, url: str):
        self.url = url
        self.connection = None
        self.lock = threading.Lock()
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.last_connect_time = 0
        self.min_reconnect_interval = 5  # 最小重连间隔(秒)

    def get_connection(self) -> Connection:
        with self.lock:
            current_time = time.time()
            
            # 检查连接状态
            if (self.connection is None or 
                not self.connection.connected or
                current_time - self.last_connect_time > 3600):  # 1小时后重连
                self.connect()
            
            return self.connection

    def connect(self):
        current_time = time.time()
        
        # 防止频繁重连
        if (current_time - self.last_connect_time < self.min_reconnect_interval and
            self.reconnect_attempts > 0):
            raise Exception("重连间隔太短，请稍后重试")
        
        try:
            if self.connection:
                try:
                    self.connection.release()
                except Exception:
                    pass
            
            self.connection = Connection(self.url)
            self.connection.connect()
            self.reconnect_attempts = 0
            self.last_connect_time = current_time
            logger.info("RabbitMQ连接建立成功")
            
        except Exception as e:
            self.reconnect_attempts += 1
            logger.error(f"RabbitMQ连接失败 (尝试 {self.reconnect_attempts}/{self.max_reconnect_attempts}): {e}")
            
            if self.reconnect_attempts >= self.max_reconnect_attempts:
                logger.error("达到最大重连次数，停止重连")
            raise

    def close(self):
        with self.lock:
            if self.connection:
                try:
                    self.connection.release()
                    logger.info("RabbitMQ连接已关闭")
                except Exception as e:
                    logger.error(f"关闭RabbitMQ连接时出错: {e}")
                finally:
                    self.connection = None


class QueueKombuConnectionManager:
    """优化的Kombu连接池管理器"""
    
    def __init__(self, url: str, pool_size: int = 10):
        self.url = url
        self.pool_size = pool_size
        self.connections = []
        self.lock = threading.Lock()
        self.created_connections = 0
        self.initialize()

    def initialize(self):
        with self.lock:
            # 延迟初始化，按需创建连接
            self.connections = []
            self.created_connections = 0

    def get_connection(self) -> Connection:
        with self.lock:
            if self.connections:
                return self.connections.pop()
            elif self.created_connections < self.pool_size:
                connection = Connection(self.url)
                self.created_connections += 1
                return connection
            else:
                # 池已满，创建临时连接
                return Connection(self.url)

    def release_connection(self, connection: Connection):
        with self.lock:
            if len(self.connections) < self.pool_size:
                try:
                    # 检查连接是否仍然有效
                    if connection.connected:
                        self.connections.append(connection)
                    else:
                        connection.release()
                        self.created_connections = max(0, self.created_connections - 1)
                except Exception:
                    connection.release()
                    self.created_connections = max(0, self.created_connections - 1)
            else:
                connection.release()

    def close(self):
        with self.lock:
            for connection in self.connections:
                try:
                    connection.release()
                except Exception:
                    pass
            self.connections.clear()
            self.created_connections = 0
            logger.info("Kombu连接池已关闭")


# 全局连接管理器实例
queue_conn_manager = QueueConnectionManager(
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

# 日志配置
if not debug:
    log.LOG_CONF["handlers"]["console"]["level"] = "WARNING"
logging.config.dictConfig(log.LOG_CONF)
