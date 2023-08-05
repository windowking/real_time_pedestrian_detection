#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File: video_getter.py
Desc: 摄像头获取部分
Author: gaoy
Time: 2023/8/3
"""
import cv2
import logging
import numpy as np
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from queue import Queue
from threading import Lock, Thread
from tools.waiting_queue import WaitingQueue


class VideoGetter:
    """视频获取类.
    实现视频图片按一定 FPS 使用线程池获取.

    Args:
        fps (int).
        cfg_rtsp (dict): rtsp相关配置.
        channel (str): 视频频道号, 即 camera id.
        max_workers (int): 图片获取线程池最大线程数.
    """
    def __init__(self, fps: int, cfg_rtsp: dict, channel: str, exc_bucket, max_workers=3):
        self.fps = fps
        self.cfg_rtsp = cfg_rtsp
        self.channel = channel
        self.exc_bucket = exc_bucket
        self.max_workers = max_workers

        self.logger = logging.getLogger('log')
        self.waiting_queue = WaitingQueue(maxsize=3)  # 小一些防止淤积过度造成反应巨慢

        self.frame = None  # app_stream 抓取的每帧图像存于此
        self.frametimestamp = time.time()  # 上次抓帧时间
        self.frame_mutex = Lock()
        self.cap = None  # 流抓取器
        self.link = ''

        self.is_moving = True  # 摄像头下是否运动

    def _init_rtsp_link(self):
        """初始化 rtsp 链接."""
        try:
            if self.channel == 0:
                self.link = 0
                return
            name = self.cfg_rtsp['NAME']
            pwd = self.cfg_rtsp['PWD']
            ip = self.cfg_rtsp['IP']
            port = self.cfg_rtsp['PORT'] if 'PORT' in self.cfg_rtsp else 554

            self.link = f"rtsp://{name}:{pwd}@{ip}:{port}/Streaming/Channels/101"
            #self.link = 0#"http://devimages.apple.com/iphone/samples/bipbop/gear1/prog_index.m3u8" #测试视频

        except KeyError as err:
            self.logger.error('摄像头 {channel} 配置了错误的 RTSP 信息!'
                ' 请保证 CAMERA.DEVICES.{channel} 配置了相应的 NAME/PWD/IP.'
                '详细错误: {info}'.format(channel=self.channel, info=err))
            raise

    def _init_video_cap(self, path):
        """[DEBUG] 初始化本地视频准备抓取."""
        self.cap = cv2.VideoCapture(path)
        self.per_score = 1 / 25 * self.fps
        self.frame_count = 1  # 满1则抓一张图. 从1开始可以把第一帧算上

    def _get_img_from_video(self) -> np.ndarray:
        """[DEBUG] 抓取本地视频的图像帧."""
        success, frame = self.cap.read()
        while self.frame_count < 1:
            self.frame_count += self.per_score
            success, frame = self.cap.read()
        self.frame_count -= 1
        if not success:
            self.logger.warning('本地视频取完了, 开始阻塞.')
            time.sleep(100000)
            return None
        return frame

    def fetch_img(self, timestamp: float):
        """获取一张视频流图片."""
        with self.frame_mutex:
            imgarr = self.frame
            frametimestamp = self.frametimestamp
        if imgarr is None or timestamp - frametimestamp > 1:  # 图空或抓图卡住
            self.waiting_queue.removestamp(timestamp)
        else:
            self.logger.debug('{} fetched img (time={}).'.format(self.channel, frametimestamp))
            self.waiting_queue.putitem(timestamp, imgarr)

    def app_stream(self):
        """使用该线程不停获取每帧图片, 刷新式存放在 self.frame, app 线程负责隔时取用."""
        time_error_waiting = 10  # 出错重连间隔
        max_error_waiting = 600  # 最久重连间隔
        timeout = 1  # 判断open失败重连间隔
        timeout_max = 60  # 最久
        while True:
            # 连接 rtsp
            try:
                if self.cap:
                    self.cap.release()  # 曾连接则需释放
                self.cap = cv2.VideoCapture(self.link)
                time_error_waiting = 10
                self.logger.info(f'摄像头 {self.channel} 连接成功, 等带验证开启状态.')
            except Exception as err:
                self.logger.error(f'摄像头 {self.channel} 无法连接! 地址: {self.link}. 详细信息: {err}.')
                time.sleep(time_error_waiting)
                time_error_waiting = min(max_error_waiting, time_error_waiting * 4)  # 每次出错则时延4倍
                continue
            
            # 判断 cap 是否打开
            try:
                for i in range(timeout):
                    time.sleep(1)
                    if self.cap.isOpened():
                        self.logger.info(f'摄像头 {self.channel} 连接成功且已打开, 开始取帧.')
                        timeout = 1
                        break
                    else:
                        # 超时
                        if i >= timeout - 1:
                            raise TimeoutError()
            except TimeoutError as err:
                self.logger.warning(f'摄像头 {self.channel} 连接成功, 但是读取超时, 可能没有打开! 开始重新连接. 地址: {self.link}')
                timeout = min(timeout_max, timeout * 2)  # 二进制指数退火
                continue

            # 不停抓视频
            try:
                consiquent_fail = 0  # 连续失败帧数
                max_consiquent_fail = 250  # 最大连续失败帧数
                while True:
                    ret, frame = self.cap.read()
                    # 取流失败
                    if not ret:
                        consiquent_fail += 1
                        if consiquent_fail >= max_consiquent_fail:
                            break  # 失败过量则重连 cap
                    # 取流成功
                    else:
                        consiquent_fail = 0
                        with self.frame_mutex:
                            self.frame = frame
                            self.frametimestamp = time.time()
            except Exception as err:
                self.logger.error(f'摄像头 {self.channel} 取流时发生错误: {err}')
                continue


    def app(self):
        """app_stream 线程不停取 rtsp 帧, 本线程隔时拿一帧来."""
        try:
            self._init_rtsp_link()
            delt_sec = 1 / self.fps
            while True:
                while not self.is_moving:  # 没有运动则等待
                    time.sleep(0.1)
        
                timestamp = time.time()
                self.waiting_queue.putstamp(timestamp)
                self.fetch_img(timestamp)
                time.sleep(delt_sec)
        except Exception:
            self.exc_bucket.put(sys.exc_info())

    def app_debug(self):
        """[DEBUG] 用视频来预测, 而非摄像头."""
        try:
            self._init_video_cap(self.channel)
            pool = ThreadPoolExecutor(max_workers=self.max_workers)  # 图片获取线程池
            while True:
                timestamp = datetime.now().timestamp()
                self.waiting_queue.putstamp(timestamp)
                imgarr = self._get_img_from_video()
                self.waiting_queue.putitem(timestamp, imgarr)
                time.sleep(0.2)
        except Exception:
            self.exc_bucket.put(sys.exc_info())

    def run(self):
        # 测试的本地视频
        if isinstance(self.channel, str) and self.channel.split('.')[-1] in ['avi', 'wmv', 'mpeg', 'mp4', 'm4v', 'mov', 'asf', 'flv', 'f4v', 'rmvb', 'rm', '3gp', 'vob']:
            thread = Thread(target=self.app_debug)
            thread.start()
        # 生产环境 rtsp 流
        else:
            thread_getter = Thread(target=self.app_stream)
            thread_cutter = Thread(target=self.app)
            thread_getter.start()
            thread_cutter.start()

    def get(self, **args):
        """获取图片队列按顺序排列好的图片们.

        Camera 对象通过该方式不停获取图片.
        
        Args:
            **args: 参数同 Queue.
        Returns:
            timestamp: int.
            imgarr: np.ndarray.
        """
        return self.waiting_queue.get_with_stamp(**args)
