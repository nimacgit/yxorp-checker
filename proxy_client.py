import requests
import time
from loguru import logger

class ProxyProvider:
    example_headers = {
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.87 Safari/537.36',
        'referrer': 'https://google.com',
        'Accept': '*/*',
        'Accept-Encoding': '*', #'gzip, deflate, br',
#         'Pragma': 'no-cache',
    }
    
    def __init__(self, ipport="0.0.0.0:8008"):
        self.ipport=ipport
    
    def get_bad_proxy(self, protocol):
        while True:
            try:
                return requests.get(f"http://{self.ipport}/get_bad_proxy/{protocol}").json()["proxy"]
            except:
                logger.debug("cant get from proxy")
                time.sleep(0.5)
    
    def get_proxy(self, protocol, retry=-1):
        while retry != 0:
            retry -= 1
            try:
                return requests.get(f"http://{self.ipport}/get_proxy/{protocol}").json()["proxy"]
            except:
                logger.debug("cant get from proxy")
                time.sleep(0.5)
    
    def bad_ip(self, protocol, ip):
        while True:
            try:
                return requests.get(f"http://{self.ipport}/bad_ip/{protocol}/{ip}").json()
            except:
                logger.debug("cant send bad ip")
                time.sleep(0.5)

                
    def change_priority(self, protocol, src_p, dst_p):
        while True:
            try:
                return requests.get(f"http://{self.ipport}/chng_p/{protocol}/{src_p}/{dst_p}").json()
            except:
                logger.debug("cant change priority")
                time.sleep(0.5)

    def move_priority(self, protocol, src_p, dst_p, count):
        while True:
            try:
                return requests.get(f"http://{self.ipport}/move_p/{protocol}/{src_p}/{dst_p}/{count}").json()
            except:
                logger.debug("cant move priority")
                time.sleep(0.5)
                
    def get_stats(self, protocol):
        while True:
            try:
                return requests.get(f"http://{self.ipport}/stat/{protocol}").json()
            except:
                logger.debug("cant get stats")
                time.sleep(0.5)

    def add_ip(self, protocol, ipport):
        while True:
            try:
                return requests.get(f"http://{self.ipport}/add_ip/{protocol}/{ipport}").json()
            except:
                logger.debug("cant add ip")
                time.sleep(0.5)

    def add_ip_bulk(self, protocol, ipports):
        while True:
            try:
                return requests.post(f"http://{self.ipport}/add_ip_bulk/{protocol}", json=ipports).json()
            except:
                logger.debug("cant add bulk ip")
                time.sleep(0.5)
    
    def save_to_file(self):
        while True:
            try:
                return requests.get(f"http://{self.ipport}/save").json()
            except:
                logger.debug("cant save")
                time.sleep(0.5)
    
    def get_link(self, url, protocol=None, retry=-1):
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Cafari/537.36'}
        if retry < 0:
            retry = -10
        r = None
        if not protocol:
            protocol = url.split("://")[0]
        
        while retry == -10 or retry >= 0:
            proxies = {protocol: self.get_proxy(protocol)}
            try:
                r = requests.get(f"{protocol}://google.com", headers=headers, proxies=proxies, timeout=10)
                if "google.com" in r.text:
                    r = requests.get(url, headers=headers, proxies=proxies, timeout=10)
                    if r.status_code != 200:
                        self.bad_ip(protocol, proxies[protocol])
                        logger.debug("retry getting")
                    else:
                        return r
                else:
                    self.bad_ip(protocol, proxies[protocol])
                    logger.debug("retry getting")
            except:
                self.bad_ip(protocol, proxies[protocol])
                logger.debug("retry getting")
            retry = max(-10, retry - 1)
        return r
    
    def get_proxy_for_link(self, url, protocol=None, retry=-1):
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Cafari/537.36'}
        if retry < 0:
            retry = -10
        r = None
        if not protocol:
            protocol = url.split("://")[0]
        
        while retry == -10 or retry >= 0:
            proxies = {protocol: self.get_proxy(protocol)}
            try:
                r = requests.get(f"{protocol}://google.com", headers=headers, proxies=proxies, timeout=10)
                if "google.com" in r.text:
                    r = requests.get(url, headers=headers, proxies=proxies, timeout=10)
                    if r.status_code != 200:
                        self.bad_ip(protocol, proxies[protocol])
                        logger.debug("retry getting")
                    else:
                        return proxies[protocol]
                else:
                    self.bad_ip(protocol, proxies[protocol])
                    logger.debug("retry getting")
            except:
                self.bad_ip(protocol, proxies[protocol])
                logger.debug("retry getting")
            retry = max(-10, retry - 1)
        return None
        
        