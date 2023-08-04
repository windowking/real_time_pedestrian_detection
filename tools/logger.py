#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File: logger.py
Desc: 日志模块
Author: gaoy
Time: 2023/8/3
"""
import os
import os.path as op
import logging
import re
import sys
from logging.handlers import TimedRotatingFileHandler

main_dir = op.abspath(op.join(op.dirname(op.abspath(__file__)), ".."))  # 项目主目录


def setup_log(log_name="log"):
    """python日志按天分割，保存近一个月日志

    如果其他 py 文件想使用此配置日志，只需 logging.getLogger(日志的名字)  即可
    From: https://www.cnblogs.com/xujunkai/p/12364619.html

    Args:
        log_name: str, log 文件前缀名.
    """
    logger = logging.getLogger(log_name)
    logger.setLevel(logging.INFO)

    log_path = op.join(op.join(main_dir, "logs"), log_name + ".log")
    if not op.exists(op.dirname(log_path)):
        os.makedirs(op.dirname(log_path))

    # console stdout
    ch = logging.StreamHandler(stream=sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(
        logging.Formatter(
            "[%(asctime)s] [%(process)d] [%(levelname)s] - %(module)s.%(funcName)s (%(filename)s:%(lineno)d) - %(message)s"
        )
    )
    logger.addHandler(ch)

    # 30 days rotating log clean
    file_handler = TimedRotatingFileHandler(
        filename=log_path, when="MIDNIGHT", interval=1, backupCount=30, encoding="utf8"
    )
    file_handler.suffix = "%Y-%m-%d.log"
    file_handler.extMatch = re.compile(r"^\d{4}-\d{2}-\d{2}.log$")
    file_handler.setFormatter(
        logging.Formatter(
            "[%(asctime)s] [%(process)d] [%(levelname)s] - %(module)s.%(funcName)s (%(filename)s:%(lineno)d) - %(message)s"
        )
    )
    logger.addHandler(file_handler)

    return logger


if __name__ == "__main__":
    logger = setup_log()
    logger.debug("this is a debug message")
    logger.info("this is an info message")
    logger.warning("this is a warning message")
    logger.error("this is an error message")
    logger.fatal("this is a fatal message")
    try:
        int("xjk")
    except ValueError as e:
        logger.error(e)
