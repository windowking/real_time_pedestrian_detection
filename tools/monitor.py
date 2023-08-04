#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File: monitor.py
Desc: 监控模块
Author: gaoy
Time: 2023/8/3
"""
import logging
import sys
import time
import threading

logger = logging.getLogger('log')

class Monitor():
    """
    监控类, 使用该类可对程序部分内容进行监控, 并输出到日志中.
    """
    def __init__(self, exc_bucket):
        self.max_time_gap = 3600
        self.exc_bucket = exc_bucket

    def check_queue(self, qname: str, q):
        """检查一个 queue 并输出检查结果."""
        qsize = q.qsize()
        if hasattr(q, 'maxsize'):
            maxsize = q.maxsize
        elif hasattr(q, '_maxsize'):
            maxsize = q._maxsize
        else:
            maxsize = 'unknown'

        if qsize < 32:
            logger.debug('monitor checking: {}.qsize()=={}/{}.'.format(qname, qsize, maxsize))
            return 'ok'
        else:
            logger.warning('monitor checking: {}.qsize()=={}/{}. Queue is too full.'.format(qname, qsize, maxsize))
            return 'warning'

    def app(self, qs: dict):
        try:
            timegap = 10
            while True:
                time.sleep(timegap)
                if timegap < self.max_time_gap:
                    timegap *= 2
                
                # 检查队列使用情况
                for qname, q in qs.items():
                    status = self.check_queue(qname, q)
                    if status == 'warning':
                        timegap = 10
        except Exception:
            self.exc_bucket.put(sys.exc_info())

    def run(self, qs: dict):
        """
        Args:
            qs (dict): 待检查的队列组. k=name, v=the queue.
        """
        self.thread = threading.Thread(target=self.app, args=(qs,))
        self.thread.start()
        logger.info('monitor ok.')