from requests_html import AsyncHTMLSession
from datetime import datetime, timedelta
from proxy_client import ProxyProvider
from multiprocessing import Process
from bs4 import BeautifulSoup
from loguru import logger
import aio_pika as aiop
import tracemalloc
import threading
import asyncio
import requests
import json
import time
import abc
import re
import os


'''
			http://spys.one
			https://free-proxy-list.net/
			https://www.sslproxies.org/
			https://www.freeproxy.world/
			https://github.com/TheSpeedX/PROXY-List
			https://github.com/chill117/proxy-lists/tree/master/sources
			https://github.com/clarketm/proxy-list/blob/master/proxy-list.txt
			https://github.com/Undercore/ProxyScraper.py/blob/master/SourceCode.py
'''

class IPParser(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def get_proxies(self):
        pass

EXAMPLE_HEADER = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
    "If-Modified-Since": (datetime.now() - timedelta(hours=10)).strftime("%a, %d %b %Y %H:%M:%S GMT"),
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:83.0) Gecko/20100101 Firefox/83.0",
}

OpenproxySpaceURLListHeader = {
    "Autority": "api.openproxy.space",
    "Method": "GET",
    "Path": "",
    "Scheme": "https",
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://openproxy.space",
    "Referer": "https://openproxy.space/",
    "Sec-Ch-Ua": '"Google Chrome";v="87", " Not;A Brand";v="99", "Chromium";v="87"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Fetch-dest": "empty",
    "Sec-Fetch-mode": "cors",
    "Sec-Fetch-site": "same-site",
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:83.0) Gecko/20100101 Firefox/83.0",
}


class IPParserForOpenproxySpace():
    baseurl = "https://api.openproxy.space/"
    
    def _get_proxy_list_urls(self):
        path = f"list?skip=0&ts={int(time.time()*1000)}"
        url = self.baseurl + path
        header = OpenproxySpaceURLListHeader
        header['Path'] = path        
        try:
            res = requests.get(url, timeout=15, headers=header)
            if res.status_code == 200:
                slugs = self._get_pages_slugs(res)
                urls = [f"https://openproxy.space/list/{s}" for s in slugs]
                return urls
            else:
                logger.info(f"status is not 200 link OpenproxySpace {url}")
        except Exception as E:
            logger.debug(f"Exp in get from OpenproxySpace: _get_proxy_list_urls {E}")
        return []

    def _get_pages_slugs(self, res):
        data = json.loads(res.text)
        slugs = [d['code'] for d in data]
        return slugs
    
    def _get_ips_from_openproxy(self, html):
        ip_list = []
        if not html:
            return []
        soup = BeautifulSoup(html, 'html.parser')
        ip_candidates = re.findall(r'[0-9]+(?:\.[0-9]+){3}:[0-9]+', str(html))
        return ip_candidates
    
    def get_proxies(self):
        proxy_list_urls = self._get_proxy_list_urls()
        ipports = []
        for proxy_list_url in proxy_list_urls:
            try:
                res = requests.get(proxy_list_url, timeout=15, headers=EXAMPLE_HEADER)
                if res.status_code == 200:
                    ipports = ipports + self._get_ips_from_openproxy(res.text)
                else:
                    logger.info(f"status is not 200 link OpenproxySpace {proxy_list_url}")
            except Exception as E:
                logger.debug(f"Exp in get from OpenproxySpace: get_proxies {E}")
        return list(set(ipports))
    
    
class IPParserForKuaidaili():
    def _get_ips_from_kuaidaili(self, html):
        ip_list = []
        soup = BeautifulSoup(html, 'html5lib')
        table = soup.body.find("table")
        rows = table.find_all('tr')
        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 2:
                continue
            ip = cols[0]
            port = cols[1]
            ip_candidates = re.findall(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", str(ip))
            if not ip_candidates or len(ip_candidates) < 1:
                continue
            new_ip = f'{ip_candidates[0]}:{port.text.strip()}'
            ip_list.append(new_ip)
        return ip_list

    def get_proxies(self, from_page=1, to_page=40, sleep_time_betweet_requests=2):
        ipports = []
        for i in range(from_page, to_page):
            time.sleep(sleep_time_betweet_requests)
            try:
                url = f"https://www.kuaidaili.com/free/inha/{i}/"
                res = requests.get(url, timeout=15, headers=EXAMPLE_HEADER)
                if res.status_code == 200:
                    ipports = ipports + self._get_ips_from_kuaidaili(res.text)
                else:
                    logger.info(f"status is not 200 kuaidaili link {url}")
            except Exception as E:
                logger.debug(f"Exp in get from kuaidaili: get_proxies {E}")
        return list(set(ipports))


class RParser():
    def __init__(self):
        self.file_name = "./reza_sites.txt"

    def _get_site_urls_one_by_one_from_file(self):
        try:
            f = open(self.file_name, 'r')
            counter = 0
            while True:
                data = f.readline()
                if not data:
                    break
                data = data.strip()
                yield data
        except:
            logger.info("cant open or parse file rparser")
            return []

    def _get_ips_from_page(self, html):
        ip_list = []
        soup = BeautifulSoup(html, 'html5lib')
        table = soup.body.find("table")
        rows = table.find_all('tr')
        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 2:
                continue
            ip = cols[0]
            port = cols[1]
            ip_candidates = re.findall(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", str(ip))
            if not ip_candidates or len(ip_candidates) < 1:
                continue
            new_ip = f'{ip_candidates[0]}:{port.text.strip()}'
            ip_list.append(new_ip)

        return ip_list

    def get_proxies(self):
        ips_set = set()
        for url in self._get_site_urls_one_by_one_from_file():
            try:
                if url != "":
                    logger.debug(f"{url}")
                    res = requests.get(url, headers=EXAMPLE_HEADER, timeout=15)
                    if res.status_code == 200:
                        ip_list = self._get_ips_from_page(res.text)
                        ips_set.update(ip_list)
                    else:
                        logger.info(f"status is not 200 link RProxy {url}")
                    time.sleep(1)
            except:
                logger.info(f"Exception in get_ips RProxy {url}")
        return list(ips_set)


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
        self.parsers = [IPParserForOpenproxySpace(), RParser(), IPParserForKuaidaili()]
        
    
    def _add_proxy_list(self, protocol, ipports):
        self.proxy_provider.add_ip_bulk(protocol, ipports)
    
    async def _add_pubproxy(self):
        try:
            if len(self.ip_q["https"]) > 10:
                proxies = {"https": self.proxy_provider.get_proxy("https")}
            else:
                proxies = None
            self._add_proxy_list("https", [(await self.asession.get("https://pubproxy.com/api/proxy?type=https&speed=15&https=true", timeout=15, proxies=proxies)).json()["data"][0]["ipPort"]])
            self._add_proxy_list("http", [(await self.asession.get("https://pubproxy.com/api/proxy?type=https&speed=15&https=true", timeout=15, proxies=proxies)).json()["data"][0]["ipPort"]])
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
            self.proxy_provider.save_to_file()
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
            for parser in self.parsers:
                logger.debug(f"parsing using: {parser.__class__.__name__}")
                ipports = parser.get_proxies()
                logger.debug(f"got {len(ipports)} proxy")
                self._add_proxy_list("https", ipports)
                self._add_proxy_list("http", ipports)
            logger.info("updated rproxy")
            await self._add_proxy_url()
            logger.info("updated url")
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