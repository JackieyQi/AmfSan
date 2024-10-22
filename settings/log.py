# -*- coding:utf-8 -*-

import os

path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LOG_CONF = {
    'version': 1,
    'disable_existing_loggers': False,  # this fixes the problem

    'formatters': {
        'standard': {
            'format': "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s",
            'datefmt': "%Y-%m-%d %H:%M:%S"
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'standard'
        },
        'file': {
            'level': 'INFO',
            # 'class': 'logging.FileHandler',
            'class': 'common.log.QueueHandler',

            'filename': path + "/logs/output.log",
            'when': 'D',
            "encoding": "utf8",
            'formatter': 'standard'
        },
        'tasks': {
            'level': 'INFO',
            'class': 'logging.handlers.TimedRotatingFileHandler',

            'filename': path + "/logs/queue.log",
            'when': 'D',
            "encoding": "utf8",
            'formatter': 'standard'
        },
        'sms': {
            'level': 'INFO',
            'class': 'logging.handlers.TimedRotatingFileHandler',

            'filename': path + "/logs/sms.log",
            'when': 'D',
            "encoding": "utf8",
            'formatter': 'standard'
        },
        'idverify': {
            'level': 'INFO',
            'class': 'logging.handlers.TimedRotatingFileHandler',

            'filename': path + "/logs/idverify.log",
            'when': 'D',
            "encoding": "utf8",
            'formatter': 'standard'
        }
    },
    'loggers': {
        'controllers': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
        },
        'models': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
        },
        'backends': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
        },
        'tasks': {
            'handlers': ['console', 'tasks'],
            'level': 'DEBUG',
        },
        'sms': {
            'handlers': ['console', 'sms'],
            'level': 'DEBUG',
        },
        'services': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
        },
        'idverify': {
            'handlers': ['console', 'idverify'],
            'level': 'DEBUG',
        },
        # 'peewee': {
        #    'handlers': ['console'],
        #    'level': 'DEBUG',
        # }
    }
}

LOG_SANIC_CONF = {
    'version': 1,
    'disable_existing_loggers': False,  # this fixes the problem

    'formatters': {
        'standard': {
            'format': "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s",
            'datefmt': "%Y-%m-%d %H:%M:%S",
            "class": "logging.Formatter"
        },
        "access": {
            "format": "[%(asctime)s] %(levelname)s [%(name)s][%(host)s]: " +
                      "%(request)s %(message)s %(status)d %(byte)d",
            'datefmt': "%Y-%m-%d %H:%M:%S",
            "class": "logging.Formatter"
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'standard'
        },
        'access': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': path + "/logs/access.log",
            "encoding": "utf8",
            'formatter': 'access'
        },
        'access_console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'access'
        },
        'error': {
            'level': 'INFO',
            # 'class': 'logging.FileHandler',
            'class': 'common.log.QueueHandler',

            'filename': path + "/logs/output.log",
            'when': 'D',
            "encoding": "utf8",
            'formatter': 'standard'
        },
    },
    'loggers': {
        'root': {
            'handlers': ['console', 'error'],
            'level': 'INFO',
        },
        'sanic.error': {
            'handlers': ['console', 'error'],
            'level': 'INFO',
        },
        'sanic.access': {
            'handlers': ['access_console', 'access'],
            'level': 'INFO',
        }
    }
}
