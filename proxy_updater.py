from requests_html import AsyncHTMLSession
from proxy_client import ProxyProvider
from multiprocessing import Process
from loguru import logger
import aio_pika as aiop
import tracemalloc
import threading
import asyncio
import json
import time
import re
import os



class ProxyUpdater:
    def __init__(self):
        self.is_firt_time = True
        self.proxy_provider = ProxyProvider()
        self.PROTOCOLS = ["https", "http", "socks5"]
        self.last_pubproxy_time = time.time()
        self.last_scylla_time = time.time()
        self.last_save_time = time.time()
        self.last_proxy_url_time = time.time()
        self.asession = AsyncHTMLSession()
    
    def _add_proxy_list(self, protocol, ipports):
        self.proxy_provider.add_ip_bulk(protocol, ipports)
    
    async def _add_pubproxy(self):
        try:
            if len(self.ip_q["https"]) > 10:
                proxies = {"https": self.proxy_provider.get_proxy("https")}
            else:
                proxies = None
            self._add_proxy_list("https", [(await self.asession.get("https://pubproxy.com/api/proxy?type=https&speed=15&https=true", timeout=15, proxies=proxies)).json()["data"][0]["ipPort"]])
        except:
            logger.info("pubproxy failed")
        pass
    
    async def _add_scylla(self):
        try:
            all_p = list((await self.asession.get("http://localhost:8899/api/v1/proxies?https=true&limit=10000", timeout=10)).json()["proxies"])
            ipports = [f'{p["ip"]}:{p["port"]}' for p in all_p]
            self._add_proxy_list("https", ipports)
            all_p = list((await self.asession.get("http://localhost:8899/api/v1/proxies?https=false&limit=10000", timeout=10)).json()["proxies"])
            ipports = [f'{p["ip"]}:{p["port"]}' for p in all_p]
            self._add_proxy_list("http", ipports)
        except:
            logger.info("scylla failed")

    async def _add_proxy_url(self):
        urls = []
        file_name = "proxy_url.txt"
        if os.path.isfile(file_name):
            with open(file_name, "r") as f:
                for line in f.readlines():
                    urls.append(line[:-1])
        logger.info(f"number of proxy url {len(urls)}")
        for url in urls:
            logger.debug(f"update {url}")
            try:
                if len(self.ip_q["https"]) > 10:
                    proxies = {"https": self.proxy_provider.get_proxy("https", retry=5)}
                else:
                    proxies = None
                resp = await self.asession.get(f"https://{url}", timeout=15, proxies=proxies)
                regs = re.findall(r'((?:\d{1,3}\.){3}\d{1,3}):(\d+)', resp.text)
                for protocol in self.PROTOCOLS:
                    ipports = [f"{p[0]}:{p[1]}" for p in regs]
                    self._add_proxy_list(protocol, ipports)
                logger.debug(f"done url {url}")
            except:
                try:
                    if len(self.ip_q["http"]) > 10:
                        proxies = {"http": self.proxy_provider.get_proxy("https", retry=5)}
                    resp = await self.asession.get(f"http://{url}", timeout=15, proxies=proxies)
                    regs = re.findall(r'((?:\d{1,3}\.){3}\d{1,3}):(\d+)', resp.text)
                    for protocol in self.PROTOCOLS:
                        ipports = [f"{p[0]}:{p[1]}" for p in regs]
                        self._add_proxy_list(protocol, ipports)
                    logger.debug(f"done url {url}")
                except:
                    try:
                        resp = await self.asession.get(f"https://{url}", timeout=15)
                        regs = re.findall(r'((?:\d{1,3}\.){3}\d{1,3}):(\d+)', resp.text)
                        for protocol in self.PROTOCOLS:
                            ipports = [f"{p[0]}:{p[1]}" for p in regs]
                            self._add_proxy_list(protocol, ipports)
                        logger.debug(f"done url {url}")
                    except:
                        logger.info(f"bad url https://{url}")
                        try:
                            resp = await self.asession.get(f"https://{url}", timeout=15)
                            regs = re.findall(r'((?:\d{1,3}\.){3}\d{1,3}):(\d+)', resp.text)
                            for protocol in self.PROTOCOLS:
                                ipports = [f"{p[0]}:{p[1]}" for p in regs]
                                self._add_proxy_list(protocol, ipports)
                            logger.debug(f"done url {url}")
                        except:
                            logger.info(f"bad url http://{url}")
    

    async def update_data(self):
        if time.time() - self.last_save_time > 3600:
            self.proxy_provider.save_to_file("proxies-backup")
            logger.info("save backup")
            self.last_save_time = time.time()

        if time.time() - self.last_scylla_time > 3600 or self.is_firt_time:
            await self._add_scylla()
            logger.info("updated scylla")
            self.last_scylla_time = time.time()

        if time.time() - self.last_pubproxy_time > 3600 or self.is_firt_time:
            await self._add_pubproxy()
            logger.info("updated pub")
            self.last_pubproxy_time = time.time()

        if time.time() - self.last_proxy_url_time > 3600 or self.is_firt_time:
            await self._add_proxy_url()
            logger.info("updated url")
            self.last_proxy_url_time = time.time()

        self.is_firt_time = False
    
    

        
    def adopt_proxy(self):
        logger.debug("check for good ip rate")
        res = self.proxy_provider.get_stats("https")
        total = int(res['# ip_q'])
        last = max(int(res['# last_ips']), 10)
        goods = int(res['# goods'])
        ipq = res["ips: "]
        for i in range(6, 10):
            if ipq[i] > 0:
                res = self.proxy_provider.change_priority("https", i, 12)
                del res
        if ipq[0] < 5:
            p = self.proxy_provider.move_priority("https", 5, 3, min(ipq[5], last))
            res = self.proxy_provider.change_priority("https", 3, 0)
            del p
            del res
        if goods < last * 5 and ipq[5]+ipq[4] > 10:
            res = self.proxy_provider.change_priority("https", 4, 12)
            del res
            if ipq[5] < 2*last:
                res = self.proxy_provider.change_priority("https", 12, 5)
                del res
            p = self.proxy_provider.move_priority("https", 5, 3, min(ipq[5], last))
            del p
        if goods > 10 * last and ipq[3] > 10:
            res = self.proxy_provider.move_priority("https", 3, 5, min(ipq[3], goods - 7 * last))
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
        proxy_updater.adopt_proxy()
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