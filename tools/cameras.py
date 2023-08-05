#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File: cameras.py
Desc: 摄像头模块
Author: gaoy
Time: 2023/8/4
"""
import cv2
import logging
import threading
from tools.video_getter import VideoGetter
from tools.waiting_queue import WaitingQueue
from tools.yolov5_draw import draw_bboxes
import sys
import datetime
import pytz
import numpy as np
import subprocess as sp


class Camera:
    """
    摄像头模块类
    """
    def __init__(self, name: str, fps: int, cfg_camera: dict,
            q_pic: dict, exc_bucket):
        """
        初始化函数
        Args: 
            name: 摄像头名字
            fps: 每秒抽取帧数
            cfg_camera: 摄像头配置信息
            q_pic: 待推理图片队列
        """
        self.name = name
        self.fps = fps
        self.cfg_camera = cfg_camera
        self.q_pic = q_pic
        self.exc_bucket = exc_bucket
        self.model_types = self.cfg_camera["MODEL_TYPES"]
        self.rturl = self.cfg_camera["RTMP/RTSP"]
        self.pred_waiting_queue = {}

        self.logger = logging.getLogger('log')

        self.video_getter = VideoGetter(self.fps, cfg_camera, name, self.exc_bucket)
        if not self.video_getter.channel.split('.')[-1] in ['avi', 'wmv', 'mpeg', 'mp4', 'm4v', 'mov', 'asf', 'flv', 'f4v', 'rmvb', 'rm', '3gp', 'vob']:

            self.video_getter._init_rtsp_link()
            self.cap = cv2.VideoCapture(self.video_getter.link)
        else:
            self.cap = cv2.VideoCapture(self.video_getter.channel)
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.fps = int(self.cap.get(cv2.CAP_PROP_FPS))
        self.logger.info(f"{self.width}*{self.height},{self.fps}fps")

    def send_frame(self):
        """
        发送待推理图片
        """
        try:
            for model in self.model_types:
                self.pred_waiting_queue[model] = WaitingQueue(maxsize=50)
            self.queue_ok_flag = True
            while True:
                timestamp, imgarr = self.video_getter.get()
                for model in self.model_types:
                    if model in self.q_pic.keys():
                        self.pred_waiting_queue[model].putstamp(timestamp)

                        if not self.q_pic[model].full():
                            self.q_pic[model].put((self.pred_waiting_queue[model], timestamp, imgarr))
                        else:
                            self.q_pic[model].get()
                            self.q_pic[model].put((self.pred_waiting_queue[model], timestamp, imgarr))
            
        except Exception:
            self.exc_bucket.put(sys.exc_info())

    def get_frame(self):
        """
        将预测完成的图片推流
        """
        if "rtsp" in self.rturl:
            f_type = "rtsp"
        else:
            f_type = "flv"
        
        #ffmpeg运行参数
        command = ['ffmpeg',
                '-y',
                '-f', 'rawvideo',
                '-vcodec','rawvideo',
                '-pix_fmt', 'bgr24',
                '-s', "{}x{}".format(self.width, self.height),
                '-r', str(self.fps),
                '-i', '-',
                '-c:v', 'libx264',
                '-pix_fmt', 'yuv420p',
                '-preset', 'ultrafast',
                '-f', f_type, 
                self.rturl]
        
        p = sp.Popen(command, stdin=sp.PIPE)

        while True:
            try:
                for model in self.model_types:
                    # 在这里获取帧数据 frame
                    timestamp, (imgarr, predict) = self.pred_waiting_queue[model].get_with_stamp()
                    cur_time = int(round(datetime.datetime.timestamp(datetime.datetime.now(pytz.timezone('PRC')))*1000))

                    if model == "man":
                        frame = draw_bboxes(imgarr, predict)
                        p.stdin.write(frame.tostring())

            except Exception as e:
                print("Error:", e)      
                    
    def run(self):
            """
            运行函数
            """
            self.video_getter.run()
            self.logger.info('camera {} video_getter 启动.'.format(self.name))
            
            self.queue_ok_flag = False  # pred_waiting_queue
            self.thread = threading.Thread(target=self.send_frame, args=())
            self.thread.start()
            self.logger.info('camera {} sender 线程启动.'.format(self.name))

            self.thread = threading.Thread(target=self.get_frame, args=())
            self.thread.start()
            self.logger.info('camera {} sender 线程启动.'.format(self.name))






