#! /usr/bin/env python
# coding:utf8

from sanic.exceptions import SanicException

from . import resp_code


class SanicException(Exception):
    def __init__(self, message, status_code=None, quiet=None):
        super().__init__(message)

        if status_code is not None:
            self.status_code = status_code

        # quiet=None/False/True with None meaning choose by status
        if quiet or quiet is None and status_code not in (None, 500):
            self.quiet = True


class StandardResponseExc(Exception):
	def __init__(self, data=None, msg="", code=resp_code.FAIL):
		"""
		:param code:
		:param msg:
		:param data:
		"""
		self.code = code
		self.data = data or dict()
		self.message = msg or resp_code.CODE_MESSAGES.get(code, "FAIL")


class UnAuthorizationExc(Exception):
	def __init__(self):
		self.data = dict()
		self.message = "The server could not verify that you are authorized to access the URL requested"
		self.code = resp_code.UN_AUTHORIZATION
