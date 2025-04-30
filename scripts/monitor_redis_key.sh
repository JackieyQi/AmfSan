#!/bin/bash

# Redis 配置
REDIS_HOST="127.0.0.1"
REDIS_PORT="6379"
REDIS_DB="2"
KEY_NAME="api:count"

# 日志文件配置
LOG_FILE="/tmp/amfsan_redis_monitor.log"

# 确保日志文件存在
touch "$LOG_FILE"

log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

check_redis_key() {
    # 检查key是否存在
    EXISTS=$(redis-cli -h $REDIS_HOST -p $REDIS_PORT -n $REDIS_DB EXISTS $KEY_NAME)

    if [ "$EXISTS" -eq "0" ]; then
        # log_message "Key '$KEY_NAME' 不存在，无需处理"
        return
    fi

    # 检查key的TTL
    TTL=$(redis-cli -h $REDIS_HOST -p $REDIS_PORT -n $REDIS_DB TTL $KEY_NAME)

    if [ "$TTL" -eq "-1" ]; then
        # key永久存在，需要删除
        redis-cli -h $REDIS_HOST -p $REDIS_PORT -n $REDIS_DB DEL $KEY_NAME
        log_message "Key '$KEY_NAME' 永久存在，已删除"
    # else
        # log_message "Key '$KEY_NAME' 存在且具有有效期 (TTL: $TTL)，无需处理"
    fi
}

# 主循环
while true; do
    check_redis_key
    sleep 57
done