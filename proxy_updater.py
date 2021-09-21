from parsers import IPParserForOpenproxySpace, IPParserForKuaidaili, RParser, GeneralParser, ScyllaParser, PubParser, RawParser
from proxy_client_fast import ProxyProvider
from datetime import datetime, timedelta
from multiprocessing import Process
from loguru import logger
import tracemalloc
import threading
import requests
import asyncio
import json
import time
import abc
import re
import os

class ProxyUpdater:
    def __init__(self):
        self.is_firt_time = True
        self.proxy_provider = ProxyProvider()
        self.PROTOCOLS = ["https", "http", "socks5"]
        self.last_save_time = time.time()
        self.last_proxy_url_time = time.time()
        self.parsers = [IPParserForOpenproxySpace(), RParser(), IPParserForKuaidaili(), GeneralParser(), ScyllaParser(), PubParser(), RawParser()]

    def _add_proxy_list(self, protocol, ipports):
        self.proxy_provider.add_ip_bulk(protocol, ipports)

    async def update_data(self):
        if time.time() - self.last_save_time > 3600:
            self.proxy_provider.save_to_file()
            logger.info("save backup")
            self.last_save_time = time.time()

        if time.time() - self.last_proxy_url_time > 3600 or self.is_firt_time:
            for parser in self.parsers:
                logger.debug(f"parsing using: {parser.__class__.__name__}")
                ipports = parser.get_proxies()
                logger.debug(f"got {len(ipports)} proxy")
                self._add_proxy_list("https", ipports)
                self._add_proxy_list("http", ipports)
            logger.info("updated proxy")
            self.last_proxy_url_time = time.time()
        self.is_firt_time = False
        
    def adopt_proxy(self, protocol="https"):
        logger.debug("check for good ip rate")
        res = self.proxy_provider.get_stats(protocol)
        total = int(res['# ip_q'])
        last = max(int(res['# last_ips']), 10)
        goods = int(res['# goods'])
        ipq = res["ips: "]
        if ipq[0] < 5:
            p = self.proxy_provider.move_priority(protocol, 5, 3, min(ipq[5], last))
            res = self.proxy_provider.change_priority("protocol", 3, 0)
            del p
            del res
        if goods < last * 3 and ipq[5]+ipq[4] > 10:
            res = self.proxy_provider.change_priority(protocol, 4, 12)
            del res
            if ipq[5] < 2*last:
                for i in range(6, 10):
                    if ipq[i] > 0:
                        res = self.proxy_provider.change_priority(protocol, i, 12)
                        del res
                res = self.proxy_provider.change_priority(protocol, 12, 5)
                del res
            p = self.proxy_provider.move_priority(protocol, 5, 3, min(ipq[5], 2*last))
            del p
        if goods > 5 * last and ipq[3] > 10:
            res = self.proxy_provider.move_priority(protocol, 3, 5, min(ipq[3], goods - 2 * last))
            del res

async def update_runner():
    proxy_updater = ProxyUpdater()
    logger.info("update thread start")
    while True:
        try:
            logger.info("updating")
            await proxy_updater.update_data()
            await asyncio.sleep(100)
        except:
            logger.exception("WTF Update Thread")

def adopt_runner():
    proxy_updater = ProxyUpdater()
    while True:
        for protocol in proxy_updater.PROTOCOLS:
            proxy_updater.adopt_proxy(protocol)
        time.sleep(1)

if __name__ == '__main__':
    def setup_logger(file_name):
            logger.remove()
            logger.add(f"./logs/{file_name}-debug.log", format="{time} {level} {message}", level="DEBUG", enqueue=True)
            logger.add(f"./logs/{file_name}-info.log", format="{time} {level} {message}", level="INFO", enqueue=True, backtrace=True)
            logger.add(f"./logs/{file_name}-error.log", format="{time} {level} {message}", level="ERROR", enqueue=True, backtrace=True, diagnose=True)
    setup_logger("proxy_updater")
    tracemalloc.start()
    
    p1 = Process(target=adopt_runner, args=())
    p1.start()
    asyncio.run(update_runner())