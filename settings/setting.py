#! /usr/bin/env python
# coding:utf8

import os
import json
import threading
from typing import Dict, Any, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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
        config_files = [
            f"{BASE_DIR}/settings/cfg.json",
            f"{BASE_DIR}/settings/cfg_pro.json"
        ]
        
        for config_file in config_files:
            try:
                with open(config_file) as f:
                    self._config.update(json.loads(f.read()))
                    break
            except Exception as e:
                print(f"Error loading {config_file}: {e}")

        # try:
        #     with open(f"{BASE_DIR}/settings/cfg_huobi.json") as f:
        #         self._huobi_config = json.loads(f.read())
        # except Exception as e:
        #     print(f"Error loading huobi config: {e}")
        #     self._huobi_config = None

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
