#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File: gpu_slaves.py
Desc: gpu模块
Author: gaoy
Time: 2023/8/3
"""
import logging
import os
import os.path as op
import queue
import sys
import threading
from AIDetector_pytorch import Detector

class Gpuslave:
    """
    gpu模块
    """
    def __init__(self, name: str,
            cfg_model: dict, q_pic_my: queue.Queue, exc_bucket):
        """
        初始化函数
        Args:
            name: 模型名字
            cfg_model: 模型配置信息
            q_pic_my: 待推理队列
        """
        self.name = name
        self.img_resize = 1280
        self.cfg_model = cfg_model
        self.q_pic_my = q_pic_my
        self.exc_bucket = exc_bucket
        self.threshold = 0.25
        self.stride = 32

        self.logger = logging.getLogger('log')
        self.logger.info('gpuslave({}) inited with img_resize={}.'.format(self.name, self.img_resize))

    def app(self, q_pic_my: queue.Queue, exc_bucket):
        """gpu模块主函数"""
        
        #设置使用的显卡
        if 'DEVICE' in self.cfg_model.keys():
            os.environ['CUDA_VISIBLE_DEVICES'] = self.cfg_model['DEVICE']
        
        try:
            if self.name == "man":
                #载入模型
                model = Detector(img_size = self.img_resize, cfg_model = self.cfg_model, threshold = self.threshold, stride = self.stride)
                self.logger.info('ok. Model {} loaded. Begin running.'.format(self.name))
            
        except Exception as err:
            self.logger.fatal('模型未成功部署在GPU上!详细信息: {}'.format(err.message))
            exc_bucket.put(sys.exc_info())
            return
        
        try:
            while True:
                imginfo: tuple = q_pic_my.get()
                img = imginfo[-1]
                if self.name == "man":
                    #对每张待推理图片进行推理
                    frame, predict = model.detect(img)
                    waiting_queue = imginfo[0]
                    timestamp = imginfo[1]
                    waiting_queue.putitem(timestamp, (frame, predict))
                    
        except Exception as err:
            self.logger.fatal('模型 {} 出错, 详细信息: {}'.format(self.name, err))
            self.exc_bucket.put(sys.exc_info())
    
    def run(self):
        """
        gpu模块运行函数
        """
        self.thread = threading.Thread(target=self.app, args=(self.q_pic_my, self.exc_bucket))
        self.thread.start()