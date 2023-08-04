#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File: waiting_queue.py
Desc: 自定义队列部分
Author: gaoy
Time: 2023/8/3
"""
import heapq
import logging
import multiprocessing as mp
import queue


class WaitingQueue:
    """为解决多 gpu 返还结果顺序可能不一致问题, 使用该类和时间戳管理以顺序返回结果.
    
    Args:
        mode (str): 可选 threading/processing. 创建的队列是线程级还是进程级.
        **args: Queue 的参数.
    """
    def __init__(self, mode='threading', **args):
        if mode == 'threading':
            self.queue = queue.Queue(**args)
        else:
            mngr = mp.Manager()
            self.queue = mngr.Queue(**args)
        self.logger = logging.getLogger('log')

        self.stampq = []  # 传入时间戳队列
        self.itemq = []

    def putstamp(self, stamp: float):
        """1:传入时间戳. 每个待预测图片应先传入时间戳."""
        if len(self.stampq) == 0 or stamp > self.stampq[-1]:
            self.stampq.append(stamp)
        else:
            self.logger.warning('传入的时间戳({})早于之前最晚时间戳({})! '
                '现在可以忽略该警报了.这是个理论上不可能出现的问题.'.format(
                stamp, self.stampq[-1])
            )
            self.stampq.append(stamp)
            self.stampq.sort()
                
    def putitem(self, itemstamp: float, item):
        """2:传入时间戳和项. 应使用完 putstamp() 方法后使用该方法."""

        heapq.heappush(self.itemq, (itemstamp, item))
        while len(self.itemq) > 0 and self.stampq[0] == self.itemq[0][0]:
            self.stampq.pop(0)
            self.queue.put(heapq.heappop(self.itemq))

    def removestamp(self, stamp: float):
        """2:因异常, 可删除时间戳."""
        self.stampq.remove(stamp)

    def get(self, **args) -> object:
        """3:获取队列值, 参数同 Queue.
        
        Returns:
            item: object.
        """
        return self.queue.get(**args)[1]

    def get_with_stamp(self, **args) -> tuple:
        """3:获取队列戳+值, 参数同 Queue.
        
        Returns:
            timestamp: float.
            item: object.
        """
        return self.queue.get(**args)

    def qsize(self) -> int:
        return self.queue.qsize()


if __name__ == "__main__":
    wq = WaitingQueue(maxsize=500)
    wq.putstamp(1)
    wq.putstamp(2)
    wq.putitem(2, 'hello')
    wq.putitem(1, 'hi')
    print(wq.get())
    print(wq.get())