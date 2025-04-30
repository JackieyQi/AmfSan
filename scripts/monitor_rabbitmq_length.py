#! /usr/bin/env python
# -*- coding: UTF-8 -*-


import pika
import subprocess
import time
from settings.setting import cfgs

# RabbitMQ 连接配置
RABBITMQ_HOST = cfgs["rabbitmq"]["host"]
RABBITMQ_PORT = cfgs["rabbitmq"]["port"]
RABBITMQ_USER = cfgs["rabbitmq"]["user"]
RABBITMQ_PASSWORD = cfgs["rabbitmq"]["pwd"]
QUEUE_NAME = "amf_msg"
THRESHOLD = 20
RESTART_COMMAND = ["sudo", "supervisorctl", "restart", "all"]


def get_queue_length(queue_name):
    """获取指定 RabbitMQ 队列的长度。"""
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
    parameters = pika.ConnectionParameters(
        RABBITMQ_HOST, RABBITMQ_PORT, '/', credentials
    )
    try:
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        method_frame = channel.queue_declare(queue=queue_name, passive=True)
        queue_length = method_frame.method.message_count
        connection.close()
        return queue_length
    except BaseException as e:
        print(f"连接 RabbitMQ 失败: {e}")
        return -1


def restart_supervisor():
    """执行重启 Supervisor 的命令。"""
    try:
        result = subprocess.run(RESTART_COMMAND, capture_output=True, text=True, check=True)
        print("成功重启 Supervisor:")
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"重启 Supervisor 失败: {e}")
        print(e.stderr)
    except FileNotFoundError:
        print(f"命令未找到: {RESTART_COMMAND[0]}")
    except Exception as e:
        print(f"执行命令时发生错误: {e}")


if __name__ == "__main__":
    while True:
        queue_length = get_queue_length(QUEUE_NAME)
        if queue_length != -1:
            print(f"队列 '{QUEUE_NAME}' 的当前长度: {queue_length}")
            if queue_length > THRESHOLD:
                print(f"队列 '{QUEUE_NAME}' 长度超过阈值 ({THRESHOLD})，正在尝试重启 Supervisor...")
                restart_supervisor()
                print("等待一段时间后继续监控...")
                time.sleep(60)  # 避免频繁触发重启
            else:
                print("队列长度正常。")
        time.sleep(10)  # 设置监控间隔
