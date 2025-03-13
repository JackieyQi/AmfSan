#! /usr/bin/env python
# -*- coding: UTF-8 -*-

import asyncio
import logging
import sys
import signal
import uvloop
from abc import ABC, abstractmethod
from typing import Optional, List, Callable, Any, Dict
from kombu.simple import SimpleQueue

from exts import queue_conn, amf_queue, amf_plot_queue, amf_msg_queue, amf_kline_queue, amf_tmp1_queue, amf_tmp2_queue
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
        queue_conn.connect()
        mq = queue_conn.SimpleQueue(self.queue)

        self.logger.info("Consumer started")
        print(f"Consumer started: {self.__class__.__name__}")

        while True:
            if self.restart_flag:
                self.logger.info("Consumer will quit")
                sys.exit(0)

            value = None
            try:
                # Try to get a message with non-blocking behavior
                value = mq.get(block=False, timeout=1)
                if value:
                    value.ack()
            except mq.Empty:
                # No messages in queue
                pass
            except Exception as e:
                # Handle connection issues
                self.logger.error(f"Queue error: {str(e)}")
                try:
                    queue_conn.connect()
                    mq = queue_conn.SimpleQueue(self.queue)
                except Exception as conn_err:
                    self.logger.error(f"Failed to reconnect: {str(conn_err)}")
                    await asyncio.sleep(5)  # Wait before retry

            if value:
                try:
                    await self.process_message(value.body)
                except Exception as e:
                    self.logger.error(f"Error processing message: {str(e)}")
            else:
                await asyncio.sleep(0.5)

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


class AmfTmp1Consumer(QueueConsumer):
    def __init__(self):
        super().__init__(amf_tmp1_queue, "amf_tmp1_consumer")

    async def process_message(self, message_body):
        await deal_msg(message_body)


class AmfTmp2Consumer(QueueConsumer):
    def __init__(self):
        super().__init__(amf_tmp2_queue, "amf_tmp2_consumer")

    async def process_message(self, message_body):
        await deal_msg(message_body)
