import requests
import time
from loguru import logger
import random
import aiohttp


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

    @staticmethod
    def get_random_header():
        chrome_0 = random.randint(80, 91)
        chrome_1 = random.randint(1, 4000)
        android_0 = random.randint(5, 11)
        android_1 = random.randint(0, 6)
        safari_0 = random.randint(500, 537)
        safari_1 = random.randint(1, 40)
        apple_0 = random.randint(500, 537)
        apple_1 = random.randint(1, 40)
        phone = random.choice(["Nexus 5X Build/MMB29P", "SM-G930V Build/NRD90M", "Pixel 2; DuplexWeb-Google/1.0", "Pixel 2 Build/OPD3.170816.012; Storebot-Google/1.0"])

        return {
            "user-agent": f"Mozilla/5.0 (Linux; Android {android_0}.{android_1}.1; {phone}) AppleWebKit/{apple_0}.{apple_1} (KHTML, like Gecko) Chrome/{chrome_0}.0.{chrome_1}.90 Mobile Safari/{safari_0}.{safari_1} (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
#             "Accept": "text/html,application/xhtml+xml,application/signed-exchange;v=b3,application/xml;q=0.9,*/*;q=0.8",
            'Accept': '*/*',
            "request_From": "googlebot(at)googlebot.com",
            'referrer': 'https://google.com',
        }
        

    def get_bad_proxy(self, protocol):
        while True:
            try:
                return requests.get(f"http://{self.ipport}/get_bad_proxy/{protocol}").json()["proxy"]
            except:
                logger.debug("cant get from proxy")
                time.sleep(0.5)

    async def get_proxy_async(self, protocol, retry=-1):
        session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ttl_dns_cache=3000))
        while retry != 0:
            retry -= 1
            try:
                res = await session.get(f"http://{self.ipport}/get_proxy/{protocol}")
                res = (await res.json())["proxy"]
                await session.close()
                return res
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
        headers = example_headers
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
        
        