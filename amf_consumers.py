#! /usr/bin/env python
# -*- coding: UTF-8 -*-

import asyncio
import logging
import sys
import time
import signal
import uvloop
from abc import ABC, abstractmethod
from typing import Optional, List, Callable, Any, Dict
from kombu.simple import SimpleQueue

from exts import queue_conn_manager, amf_queue, amf_plot_queue, \
    amf_msg_queue, amf_kline_queue
from msgqueue import deal_msg


class QueueConsumer(ABC):
    """所有消费者的基类"""

    def __init__(self, queue: SimpleQueue, logger_name: str):
        self.queue = queue
        self.logger = logging.getLogger(logger_name)
        self.restart_flag = False

    def setup_signal_handlers(self, signals: Optional[List[int]] = None):
        """Setup signal handlers for graceful shutdown"""
        if signals is None:
            signals = [
                signal.SIGINT,
                signal.SIGUSR2,
                signal.SIGTERM,
                signal.SIGQUIT,
                signal.SIGHUP
            ]

        for sig in signals:
            signal.signal(sig, self._handle_signal)

    def _handle_signal(self, *args, **kwargs):
        """Signal handler callback"""
        self.restart_flag = True
        self.logger.info("Consumer received shutdown signal")

    @abstractmethod
    async def process_message(self, message_body: bytes) -> None:
        """Process a message from the queue - to be implemented by subclasses"""
        pass

    async def run(self):
        """Main consumer loop"""
        connection_failures = 0
        max_connection_failures = 5
        processing_failures = 0
        max_processing_failures = 10
        backoff_time = 1

        connection = None
        mq = None

        self.logger.info("Consumer started")
        print(f"Consumer started: {self.__class__.__name__}")

        while True:
            if self.restart_flag:
                self.logger.info("Consumer will quit")
                sys.exit(0)

            if mq is None:
                try:
                    connection = queue_conn_manager.get_connection()
                    mq = connection.SimpleQueue(self.queue)
                    self.logger.info("Successfully connected to queue")
                    connection_failures = 0
                    backoff_time = 1  # 重置退避时间
                except Exception as e:
                    connection_failures += 1
                    self.logger.error(
                        f"Connection attempt {connection_failures}/{max_connection_failures} failed: {str(e)}")

                    # 计算退避时间 (指数退避)
                    backoff_time = min(30, 2 ** (connection_failures - 1))
                    self.logger.info(f"Waiting {backoff_time}s before next connection attempt")

                    if connection_failures >= max_connection_failures:
                        self.logger.critical("Max connection failures reached, waiting longer...")
                        await asyncio.sleep(60)  # 长时间等待
                        connection_failures = 0  # 重置错误计数
                    else:
                        await asyncio.sleep(backoff_time)
                    continue  # 跳过本次循环的其余部分

            value = None
            try:
                # Try to get a message with non-blocking behavior
                value = mq.get(block=False, timeout=1)
                if value:
                    value.ack()
            except mq.Empty:
                # 队列为空，正常情况
                await asyncio.sleep(0.5)
                continue
            except Exception as e:
                self.logger.error(f"Queue error: {str(e)}")
                try:
                    try:
                        if mq:
                            mq.close()
                    except:
                        pass

                    queue_conn_manager.connection = None
                    connection = queue_conn_manager.get_connection()
                    mq = connection.SimpleQueue(self.queue)
                    self.logger.info("Successfully reconnected after queue error")
                except Exception as conn_err:
                    self.logger.error(f"Failed to reconnect: {str(conn_err)}")
                    mq = None
                    await asyncio.sleep(5)  # Wait before retry
                continue

            if value:
                try:
                    await self.process_message(value.body)
                except Exception as e:
                    processing_failures += 1
                    self.logger.error(
                        f"Error processing message ({processing_failures}/{max_processing_failures}): {str(e)}")

                    if processing_failures >= max_processing_failures:
                        self.logger.warning("Too many processing failures, reconnecting to queue...")
                        try:
                            if mq:
                                mq.close()
                        except:
                            pass

                        # 通知连接管理器重置连接
                        queue_conn_manager.connection = None
                        mq = None  # 强制重连
                        processing_failures = 0  # 重置处理失败计数

    def start(self):
        """Start the consumer with asyncio event loop"""
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        self.setup_signal_handlers()

        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(self.run())
        except Exception as e:
            self.logger.error(f"Consumer error: {str(e)}")
        finally:
            loop.close()


class AmfConsumer(QueueConsumer):
    def __init__(self):
        super().__init__(amf_queue, "amf_consumer")

    async def process_message(self, message_body):
        await deal_msg(message_body)


class AmfKlineConsumer(QueueConsumer):
    def __init__(self):
        super().__init__(amf_kline_queue, "amf_kline_consumer")

    async def process_message(self, message_body):
        await deal_msg(message_body)


class AmfPlotConsumer(QueueConsumer):
    def __init__(self):
        super().__init__(amf_plot_queue, "amf_plot_consumer")

    async def process_message(self, message_body):
        await deal_msg(message_body)


class AmfMsgConsumer(QueueConsumer):
    def __init__(self):
        super().__init__(amf_msg_queue, "amf_msg_consumer")

    async def process_message(self, message_body):
        await deal_msg(message_body)
