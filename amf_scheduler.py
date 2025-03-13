#! /usr/bin/env python
# -*- coding: UTF-8 -*-

import logging
import time
import uuid
import schedule
import ujson as json
from kombu.simple import SimpleQueue
from cache import AllCache
from exts import amf_queue, amf_plot_queue, queue_conn, amf_kline_queue, amf_tmp1_queue, amf_tmp2_queue

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class JobScheduler(object):
    def __init__(self):
        self.redis_client = AllCache.get_client()

    def push_to_queue(self, queue, job_name: str, **kwargs) -> None:
        """Push a job to the specified queue with metadata"""
        # Add metadata
        payload = {
            "bp": job_name,
            "ts": int(time.time()),
            **kwargs
        }

        queue_conn.connect()
        try:
            with queue_conn.SimpleQueue(queue) as q:
                q.put(json.dumps(payload))
                logger.info(f"Scheduled job: {job_name}, kwargs: {kwargs}")
        except Exception as e:
            logger.error(f"Failed to push job {job_name} to queue: {str(e)}")
        finally:
            queue_conn.release()

    def push_to_amf(self, job_name: str, queue: SimpleQueue, **kwargs) -> None:
        if self.redis_client.get(job_name):
            logger.info(f"Skipping job {job_name} due to Redis lock")
            return

        kwargs.update({"uuid": uuid.uuid4().hex})
        self.push_to_queue(queue, job_name, **kwargs)

    def push_to_plot(self, job_name: str, **kwargs) -> None:
        self.push_to_queue(amf_plot_queue, job_name, **kwargs)

    def run(self):
        """Run the scheduler loop"""
        self.setup_schedules()
        logger.info("Scheduler started")
        print("Scheduler started")

        try:
            while True:
                schedule.run_pending()
                time.sleep(0.2)
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")
        except Exception as e:
            logger.error(f"Scheduler error: {str(e)}")

    def setup_schedules(self):
        # Data sync jobs
        # schedule.every(17).seconds.do(lambda: self.push_to_amf("sync_cache_job"))

        # Save data jobs
        schedule.every(1).minutes.do(lambda: self.push_to_amf("save_kline_job", amf_kline_queue))
        schedule.every(1).minutes.do(lambda: self.push_to_amf("save_macd_job", amf_tmp1_queue))
        schedule.every(1).minutes.do(lambda: self.push_to_amf("save_kdj_job", amf_tmp2_queue))
        # schedule.every(47).minutes.do(lambda: self.push_to_amf("save_ema_job"))

        # Technical analysis jobs
        schedule.every(30).seconds.do(lambda: self.push_to_plot("check_price_job"))
        schedule.every(3).minutes.do(lambda: self.push_to_plot("check_macd_cross_job"))
        # schedule.every(13).minutes.do(lambda: self.push_to_plot("check_macd_trend_job"))
        schedule.every(3).minutes.do(lambda: self.push_to_plot("check_kdj_cross_job"))
        # schedule.every(51).minutes.do(lambda: self.push_to_plot("check_ema_cross_job"))
        schedule.every(17).minutes.do(lambda: self.push_to_plot("check_gpt_plot_job"))

        # user action
        # schedule.every().day.at("05:00").do(save_trade_history_job)
        # schedule.every().day.at("15:27").do(check_balance_job)
        # schedule.every().day.at("03:17").do(save_account_balance_job)
        # schedule.every().day.at("15:17").do(save_account_balance_job)
        # server UTC time
        # Daily tasks
        schedule.every().day.at("00:17").do(lambda: self.push_to_amf("save_fng_job"))

