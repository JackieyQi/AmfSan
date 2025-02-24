#! /usr/bin/env python
# -*- coding: UTF-8 -*-


class BasePlotHandle(object):
    def __init__(self):
        self.result = {}

    def send_msg_unsync(self, email_title, email_content):
        if not self.result:
            return

        from business.mail_serve import send_email
        send_email([
                    "wayley@live.com",
                ], email_title, email_content)

    async def send_msg(self, email_title, email_content, receiver_list=None):
        if not self.result:
            return

        from msgqueue.queue import push_msg

        default_receiver_list = ["wayley@live.com", ]
        await push_msg(
            {
                "bp": "send_email_task",
                "receiver": default_receiver_list if not receiver_list else receiver_list,
                "title": email_title,
                "content": email_content,
            }
        )
