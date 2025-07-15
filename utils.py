from contextlib import closing
import datetime
import logging
import os
from pathlib import Path
import sqlite3

from .db import db_get_hist

class CustomFormatter(logging.Formatter):
    """Logging Formatter to add colors and count warning / errors"""
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    blue = "\x1b[36;20m"
    green = "\x1b[32;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[97;1m"
    reset = "\x1b[0m"
    # format = "%(name)s | %(levelname)s | %(message)s" # (%(filename)s:%(lineno)d)"

    FORMATS = {
        logging.DEBUG: green + "[D] %(name)s | %(filename)s:%(lineno)d | %(message)s" + reset,
        logging.INFO: blue + "[I] %(name)s | %(message)s" + reset,
        logging.WARNING: yellow + "[W] %(name)s | %(message)s" + reset,
        logging.ERROR: red + "[E] %(name)s | %(message)s" + reset,
        logging.CRITICAL: bold_red + "[C] %(name)s | %(message)s" + reset,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

class FileFormatter(logging.Formatter):
    FORMATS = {
        logging.DEBUG:    "[D] %(name)s | %(filename)s:%(lineno)d | %(message)s",
        logging.INFO:     "[I] %(name)s | %(message)s",
        logging.WARNING:  "[W] %(name)s | %(message)s",
        logging.ERROR:    "[E] %(name)s | %(message)s",
        logging.CRITICAL: "[C] %(name)s | %(message)s",
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

def setup_logger(name, file_name=None):
    handler = logging.StreamHandler()
    handler.setFormatter(CustomFormatter())
    if name in name in logging.Logger.manager.loggerDict:
        return logging.getLogger(name)
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    return logger

def get_run_id(fallback):
    try:
        __file__ = os.path.split(__file__)[-1]
        __file__ = os.path.splitext(__file__)[0]
    except NameError:
        __file__ = fallback
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    return __file__, timestamp

def setup_file_logger(fname, timestamp):
    # Set up a filehandler for all loggers (via root logger)
    p = Path('logs') / f'{fname}'
    p.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(p / f'{timestamp}.log')
    file_handler.setFormatter(FileFormatter())
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)

def setup_db(fname, timestamp):
    db_name = f'data/{fname}-db2.db'
    table_name = f'tab_{timestamp}'

    with closing(sqlite3.connect(db_name)) as db:
        hist = db_get_hist(db, table_name)
        print(hist)
    return db_name, table_name, hist