#! /usr/bin/env python
# -*- coding: UTF-8 -*-

import argparse
import sys

from amf_consumers import AmfConsumer, AmfPlotConsumer, AmfMsgConsumer
from amf_scheduler import JobScheduler


def main():
    parser = argparse.ArgumentParser(description="AMF Queue System Runner")
    parser.add_argument("component", type=str, choices=["consumer", "plot_consumer", "msg_consumer", "scheduler"],
                        help="Component to run")

    args = parser.parse_args()

    try:
        if args.component == "consumer":
            consumer = AmfConsumer()
            consumer.start()
        elif args.component == "plot_consumer":
            consumer = AmfPlotConsumer()
            consumer.start()
        elif args.component == "msg_consumer":
            consumer = AmfMsgConsumer()
            consumer.start()
        elif args.component == "scheduler":
            scheduler = JobScheduler()
            scheduler.run()
        else:
            print(f"Unknown component: {args.component}")
            sys.exit(1)
    except KeyboardInterrupt:
        print("Process terminated by user")
    except Exception as e:
        print(f"Error running {args.component}: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()

