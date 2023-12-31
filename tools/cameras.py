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


def letterbox(img, new_shape=(640, 640), color=(114, 114, 114), auto=True, scaleFill=False, scaleup=True, stride=32):
    # Resize and pad image while meeting stride-multiple constraints
    shape = img.shape[:2]  # current shape [height, width]
    if isinstance(new_shape, int):
        new_shape = (new_shape, new_shape)

    # Scale ratio (new / old)
    r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
    if not scaleup:  # only scale down, do not scale up (for better test mAP)
        r = min(r, 1.0)

    # Compute padding
    ratio = r, r  # width, height ratios
    new_unpad = int(round(shape[1] * r)), int(round(shape[0] * r))
    dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]  # wh padding
    if auto:  # minimum rectangle
        dw, dh = np.mod(dw, stride), np.mod(dh, stride)  # wh padding
    elif scaleFill:  # stretch
        dw, dh = 0.0, 0.0
        new_unpad = (new_shape[1], new_shape[0])
        ratio = new_shape[1] / shape[1], new_shape[0] / shape[0]  # width, height ratios

    dw /= 2  # divide padding into 2 sides
    dh /= 2

    if shape[::-1] != new_unpad:  # resize
        img = cv2.resize(img, new_unpad, interpolation=cv2.INTER_LINEAR)
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    img = cv2.copyMakeBorder(img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)  # add border
    return img


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
        self.output_size = self.cfg_camera["OUTPUT_SIZE"]

        self.logger = logging.getLogger('log')

        self.video_getter = VideoGetter(self.fps, cfg_camera, name, self.exc_bucket)

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
                '-s', "{}x{}".format(self.output_size, self.output_size),
                '-r', str(15),
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
                        frame = cv2.resize(frame, (self.output_size, self.output_size), interpolation=cv2.INTER_LINEAR)
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






