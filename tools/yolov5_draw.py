#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File: yolov5_draw.py
Desc: 边界框绘制
Author: gaoy
Time: 2023/8/3
"""
import cv2
import numpy as np

def draw_bboxes(image, bboxes, line_thickness=None):
    """
    边界框绘制函数
    Args:
        image: 输入图像
        bboxes: 边界框
        line_thickness: 线条宽度
    """
    tl = line_thickness or round(0.002 * (image.shape[0] + image.shape[1]) / 2) + 1
    for (x1, y1, x2, y2, lbl, conf) in bboxes:
        if lbl == "person":
            c1, c2 = (x1, y1), (x2, y2)
            color = [0, 255, 0]  # 绿色边界框

            #矩形框绘制
            cv2.rectangle(image, c1, c2, color, thickness=tl, lineType=cv2.LINE_AA)

            conf = "{:.2f}".format(np.array(conf.cpu()))
            label = f"{lbl} {str(conf)}"
            tf = max(tl - 1, 1)
            t_size = cv2.getTextSize(label, 0, fontScale=tl / 2, thickness=tf)[0]
            c2 = c1[0] + t_size[0], c1[1] - t_size[1] - 3

            # 绘制阴影效果
            shadow_color = [0, 0, 0]
            cv2.rectangle(image, (c1[0], c1[1] - t_size[1] - 3), c2, shadow_color, -1, cv2.LINE_AA)

            # 绘制标签
            cv2.putText(image, label, (c1[0], c1[1] - 2), 0, tl / 2, [255, 255, 255], thickness=tf, lineType=cv2.LINE_AA)

    return image
