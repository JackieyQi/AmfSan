#! /usr/bin/env python
# coding:utf8

import os
import threading
from typing import Dict, Any, Optional


class ConfigManager:
    _instance = None
    _lock = threading.Lock()
    _config: Dict[str, Any] = {}
    _huobi_config: Optional[Dict[str, Any]] = None

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ConfigManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._config:
            self._load_config()

    def _load_config(self):
        """Load runtime configuration from environment variables only."""
        host = self._env("AMFSAN_HOST", "0.0.0.0")
        port = self._env("AMFSAN_PORT", 8080, int)

        self._config = {
            "version": self._env("AMFSAN_VERSION", "1.0"),
            "debug": self._env("AMFSAN_DEBUG", False, self._to_bool),
            "access_log": self._env("AMFSAN_ACCESS_LOG", True, self._to_bool),
            "auto_reload": self._env("AMFSAN_AUTO_RELOAD", False, self._to_bool),
            "host": host,
            "port": port,
            "secret_key": self._required("AMFSAN_SECRET_KEY"),
            "administrator_email": self._env("AMFSAN_ADMINISTRATOR_EMAIL", ""),
            "email_sender": {
                "smtp": self._env("AMFSAN_EMAIL_SMTP", ""),
                "port": self._env("AMFSAN_EMAIL_PORT", 465, int),
                "user": self._env("AMFSAN_EMAIL_USER", ""),
                "pwd": self._env("AMFSAN_EMAIL_PASSWORD", ""),
            },
            "redis": {
                "host": self._env("AMFSAN_REDIS_HOST", "127.0.0.1"),
                "port": self._env("AMFSAN_REDIS_PORT", 6379, int),
                "db": self._env("AMFSAN_REDIS_DB", 2, int),
                "user": self._env("AMFSAN_REDIS_USER", ""),
                "pwd": self._env("AMFSAN_REDIS_PASSWORD", ""),
            },
            "database": {
                "engine": self._env("AMFSAN_DB_ENGINE", "postgresql"),
                "host": self._env("AMFSAN_DB_HOST", "127.0.0.1"),
                "port": self._env("AMFSAN_DB_PORT", 5432, int),
                "db": self._required("AMFSAN_DB_NAME"),
                "user": self._required("AMFSAN_DB_USER"),
                "pwd": self._required("AMFSAN_DB_PASSWORD"),
                "charset": self._env("AMFSAN_DB_CHARSET", "utf8mb4"),
                "schema": self._env("AMFSAN_DB_SCHEMA", "public"),
                "connections": self._env("AMFSAN_DB_CONNECTIONS", 10, int),
                "timeout": self._env("AMFSAN_DB_TIMEOUT", 30, int),
            },
            "rabbitmq": {
                "host": self._env("AMFSAN_RABBITMQ_HOST", "127.0.0.1"),
                "port": self._env("AMFSAN_RABBITMQ_PORT", 5672, int),
                "user": self._required("AMFSAN_RABBITMQ_USER"),
                "pwd": self._required("AMFSAN_RABBITMQ_PASSWORD"),
                "vhost": self._env("AMFSAN_RABBITMQ_VHOST", "/"),
                "amf_exchange": self._env("AMFSAN_RABBITMQ_EXCHANGE", "amf"),
                "default_exchange": self._env("AMFSAN_RABBITMQ_DEFAULT_EXCHANGE", "amf_default"),
            },
            "http": {
                "inner_url": self._env("AMFSAN_HTTP_INNER_URL", f"http://127.0.0.1:{port}"),
            },
            "bian": {
                "key": self._env("AMFSAN_BINANCE_KEY", ""),
                "secret": self._env("AMFSAN_BINANCE_SECRET", ""),
            },
        }
        self._validate_database_config()
        self._load_huobi_config()

    def _env(self, env_name, default=None, caster=str):
        value = os.getenv(env_name)
        if value is None or value == "":
            return default
        return caster(value)

    @staticmethod
    def _required(env_name: str) -> str:
        value = os.getenv(env_name)
        if value is None or value == "":
            raise RuntimeError(f"Missing required environment variable: {env_name}")
        return value

    def _validate_database_config(self):
        database = self._config["database"]
        engine = str(database["engine"]).lower()
        port = database["port"]
        if engine in ("postgres", "postgresql", "pg") and port == 3306:
            raise RuntimeError("Invalid database config: PostgreSQL must not use MySQL port 3306")
        if engine in ("mysql", "mariadb") and port == 5432:
            raise RuntimeError("Invalid database config: MySQL must not use PostgreSQL port 5432")

    def _load_huobi_config(self):
        public_key = os.getenv("AMFSAN_HUOBI_PUBLIC_KEY")
        secret_key = os.getenv("AMFSAN_HUOBI_SECRET_KEY")
        if public_key and secret_key:
            self._huobi_config = {
                "public_key": public_key,
                "secret_key": secret_key,
            }

    @staticmethod
    def _to_bool(value):
        return str(value).strip().lower() in ("1", "true", "yes", "on")

    @property
    def config(self) -> Dict[str, Any]:
        return self._config

    @property
    def huobi_config(self) -> Optional[Dict[str, Any]]:
        return self._huobi_config

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def reload(self):
        """重新加载配置"""
        with self._lock:
            self._config.clear()
            self._huobi_config = None
            self._load_config()


# 为了保持与现有代码的兼容性，创建全局变量
config_manager = ConfigManager()
cfgs = config_manager.config
cfgs_huobi = config_manager.huobi_config

# 重新加载配置
# config_manager.reload()
