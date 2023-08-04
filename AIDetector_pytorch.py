#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File: AIDetector_pytorch.py
Desc: yolov5检测器
Author: gaoy
Time: 2023/8/4
"""
import torch
import numpy as np
from models.experimental import attempt_load
from utils.general import non_max_suppression, scale_coords
from utils.torch_utils import select_device
from utils.datasets import letterbox


class Detector:
    """
    yolov5检测器
    """
    def __init__(self, cfg_model, threshold = 0.25, stride = 32, img_size = 1280):
        """
        初始化函数
        Args: 
            cfg_model: 模型配置信息
            threshold: 置信度阈值
            stride: 移动步长
            img_size: 新图片尺寸
        """
        self.img_size = img_size
        self.threshold = threshold
        self.stride = stride
        self.cfg_model = cfg_model
        super(Detector, self).__init__()
        self.init_model()
        
    def init_model(self):
        """
        初始化模型函数
        """
        self.weights = self.cfg_model["WEIGHTS"]
        self.device = self.cfg_model["DEVICE"]
        self.device = select_device(self.device)
        model = attempt_load(self.weights, map_location=self.device)
        model.to(self.device).eval() 
        model.half()
        self.m = model
        self.names = model.module.names if hasattr(
            model, 'module') else model.names

    def preprocess(self, img):
        """
        图片预处理函数
        Args:
            img: 传入的图片
        """
        img0 = img.copy()
        img = letterbox(img, new_shape=self.img_size, stride=self.stride)[0]
        img = img[:, :, ::-1].transpose(2, 0, 1)
        img = np.ascontiguousarray(img)
        img = torch.from_numpy(img).to(self.device)
        img = img.half()  # 半精度
        img /= 255.0  # 图像归一化
        if img.ndimension() == 3:
            img = img.unsqueeze(0)
        return img0, img

    def detect(self, im):
        """
        yolov5推理函数
        Args:
            im: 传入的图片
        """
        im0, img = self.preprocess(im)
        pred = self.m(img, augment=False)[0]
        pred = pred.float()
        pred = non_max_suppression(pred, self.threshold, 0.45, agnostic=True)
        pred_boxes = []

        for det in pred:
            if det is not None and len(det):
                det[:, :4] = scale_coords(
                    img.shape[2:], det[:, :4], im0.shape).round()
                for *x, conf, cls_id in det:
                    lbl = self.names[int(cls_id)]
                    x1, y1 = int(x[0]), int(x[1])
                    x2, y2 = int(x[2]), int(x[3])
                    pred_boxes.append(
                        (x1, y1, x2, y2, lbl, conf))
        return im, pred_boxes

