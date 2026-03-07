# 创建脚本文件
sudo nano /usr/local/bin/monitor_redis_key.sh


# 设置执行权限
sudo chmod +x /usr/local/bin/monitor_redis_key.sh


# 创建服务文件
sudo nano /etc/systemd/system/redis-key-monitor.service


#启动服务

# 重新加载 systemd 配置
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start redis-key-monitor

# 设置开机自启
sudo systemctl enable redis-key-monitor


# 查看服务状态
sudo systemctl status redis-key-monitor

# 查看日志
sudo tail -f /var/log/redis_monitor.log


# 停止服务
sudo systemctl stop redis-key-monitor

# 重启服务
sudo systemctl restart redis-key-monitor

# 禁用开机自启
sudo systemctl disable redis-key-monitor


# 确保日志文件权限正确
```
sudo touch /var/log/redis_monitor.log
sudo chown your_username:your_username /var/log/redis_monitor.log
```


# 测试 Redis 连接
redis-cli -h 127.0.0.1 -p 6379 -n 2 ping


# 监控服务运行状态
# 实时查看服务日志
sudo journalctl -u redis-key-monitor -f