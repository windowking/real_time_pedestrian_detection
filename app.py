#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File: app.py
Desc: 主程序入口
Author: gaoy
Time: 2023/8/4
"""
import yaml
import queue
import time
import traceback
import json
import logging
from tools.logger import setup_log
from tools.cameras import Camera
from tools.gpu_slaves import Gpuslave
from tools.monitor import Monitor


class Dect_App:
    """
    主程序类
    """
    def __init__(self):
        """
        初始化函数
        """
        logger = setup_log()
        self.logger = logger

        #读取配置文件内容
        with open("configs/config.yaml",'r',encoding='utf-8') as f:
            config = f.read()
            self.cfg = yaml.safe_load(config)
        logger.info('-'*10 + 'App Config' + '-'*10)
        logger.info(json.dumps(self.cfg))

        self.q_pic = {}
        self.exc_bucket = queue.Queue()
        self.gpu_slaves = {}
        self.cameras = {}

    def setup_cameras(self):
        """
        摄像头模块启动函数
        """
        self.logger.info('cameras: preparing...')
        for camera_name, camera_cfg in self.cfg['CAMERA']['DEVICES'].items():
            self.cameras[camera_name] = Camera(
                name=camera_name,
                fps=self.cfg['CAMERA']['FPS'],
                cfg_camera=camera_cfg,
                q_pic=self.q_pic,
                exc_bucket=self.exc_bucket,
            )
        for camera in self.cameras.values():
            camera.run()

    def setup_gpu_slaves(self):
        """
        GPU模块启动函数
        """
        self.logger.info('gpu slaves: preparing...')
        for model_name, model_cfg in self.cfg['MODEL']['TYPES'].items():
            model_name = model_name.lower()
            self.q_pic[model_name] = queue.Queue(maxsize=50)
            self.gpu_slaves[model_name] = Gpuslave(
                name=model_name,
                q_pic_my=self.q_pic[model_name],
                exc_bucket=self.exc_bucket,
                cfg_model = model_cfg
            )
        for slave in self.gpu_slaves.values():
            slave.run()
            time.sleep(1)

    def setup_monitor(self):
        """
        监控模块启动函数
        """
        self.logger.info('monitor: preparing...') 
        qs = {}
        for name, q in self.q_pic.items():
            qs['q_pic_trans_{}'.format(name)] = q
        for name, camera in self.cameras.items():
            qs['q_camera_{}'.format(name)] = camera.video_getter.waiting_queue.queue
        self.monitor = Monitor(self.exc_bucket)
        self.monitor.run(qs)

    def run(self):
        """
        运行总函数
        """
        self.logger.info('-'*10 + 'Dect_App Begin Running' + '-'*10)
        self.setup_gpu_slaves()
        self.setup_cameras()
        self.setup_monitor()

        e_type, e_value, e_traceback = self.exc_bucket.get()
        self.logger.fatal("type ==> %s" % (e_type.__name__))
        self.logger.fatal("value ==> %s" %(e_value))
        self.logger.fatal("traceback ==> file name: %s" %(e_traceback.tb_frame.f_code.co_filename))
        self.logger.fatal("traceback ==> line no: %s" %(e_traceback.tb_lineno))
        self.logger.fatal("traceback ==> function name: %s" %(e_traceback.tb_frame.f_code.co_name))
        self.logger.fatal(traceback.print_exception(e_type, e_value, e_traceback))
        self.logger.info('程序因故退出, 请查看日志信息.')


if __name__== "__main__":
    try:
        dect_app = Dect_App()
        dect_app.run()
    except Exception:
        logger = logging.getLogger('log')
        logger.exception('Fatal error in main.')