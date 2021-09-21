from .proxy_client_fast import ProxyProvider
from bs4 import BeautifulSoup
from loguru import logger
import tracemalloc
import requests
import datetime
import time
import json
import abc
import re
import os

'''
    https://github.com/TheSpeedX/PROXY-List
    https://github.com/chill117/proxy-lists/tree/master/sources

'''

class IPParser(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def get_proxies(self):
        pass


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
                res = requests.get(proxy_list_url, timeout=15, headers=ProxyProvider.get_random_header())
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
                res = requests.get(url, timeout=15, headers=ProxyProvider.get_random_header())
                if res.status_code == 200:
                    ipports = ipports + self._get_ips_from_kuaidaili(res.text)
                else:
                    logger.info(f"status is not 200 kuaidaili link {url}")
            except Exception as E:
                logger.debug(f"Exp in get from kuaidaili: get_proxies {E}")
        return list(set(ipports))


class RParser():
    def __init__(self):
        self.file_name = "reza_sites.txt"

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
                    res = requests.get(url, headers=ProxyProvider.get_random_header(), timeout=15)
                    if res.status_code == 200:
                        ip_list = self._get_ips_from_page(res.text)
                        ips_set.update(ip_list)
                    else:
                        logger.info(f"status is not 200 link RProxy {url}")
                    time.sleep(1)
            except:
                logger.info(f"Exception in get_ips RProxy {url}")
        return list(ips_set)


class GeneralParser():
    def __init__(self):
        self.file_name = "proxy_url.txt"

    def get_proxies(self):
        urls = []
        if os.path.isfile(self.file_name):
            with open(self.file_name, "r") as f:
                for line in f.readlines():
                    urls.append(line[:-1])
        logger.info(f"number of proxy url {len(urls)}")
        all_ipports = []
        for url in urls:
            logger.debug(f"update {url}")
            resp = None
            try:
                resp = requests.get(f"https://{url}", timeout=3, headers=ProxyProvider.get_random_header())
            except:
                pass
            if resp is None or resp.status_code != 200:
                try:
                    resp = requests.get(f"http://{url}", timeout=3, headers=ProxyProvider.get_random_header())
                except:
                    pass
            if resp is None:
                logger.info(f"cant get url {url}")
                continue
            if resp.status_code == 200:
                regs = re.findall(r'((?:\d{1,3}\.){3}\d{1,3}):(\d+)', resp.text)
                ipports = [f"{p[0]}:{p[1]}" for p in regs]
                all_ipports = all_ipports + ipports
                logger.debug(f"done url {url}")
            else:
                logger.info(f"url status code is not 200 {url}")
            
        return all_ipports

class ScyllaParser():
    def __init__(self):
        self.host_url = "http://localhost:8899/api/v1/proxies"

    def get_proxies(self):
        try:
            logger.info("scylla failed")
            all_p = list((requests.get(f"{self.host_url}?https=true&limit=10000", timeout=10)).json()["proxies"])
            ipports = [f'{p["ip"]}:{p["port"]}' for p in all_p]
            all_p = list((requests.get(f"{self.host_url}?https=false&limit=10000", timeout=10)).json()["proxies"])
            ipports = ipports + [f'{p["ip"]}:{p["port"]}' for p in all_p]
            return ipports
        except:
            return []

class PubParser():
    def __init__(self):
        self.host_url = "http://pubproxy.com/api/proxy"

    def get_proxies(self):
        try:
            return [requests.get(f"{self.host_url}?type=http&speed=15&https=false", timeout=15).json()["data"][0]["ipPort"]]
        except:
            logger.info("pubproxy failed")
            return []


class RawParser():
    def __init__(self):
        self.file_name = "raw_proxies.txt"
    
    def get_proxies(self):
        if os.path.isfile(self.file_name):
            f = open(self.file_name, "r")
            lines = f.readlines()
            return [l.replace("\n", "").strip() for l in lines if len(l) > 6]
        return []