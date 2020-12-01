from random import choice, randint
from sanic.response import json
from loguru import logger
from sanic import Sanic
import time
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

class ProxyProvider:
    PROTOCOLS = ["https", "http", "socks5"]
    def __init__(self):
        self.BUCKETS_NUMBER = 15
        self.MIN_REUSE_TIME = 30
        self.MAX_GOOD_PRIORITY = 3
        self.MAX_BAD_PRIORITY = 7
        self.NEW_IP_PRIORITY = 3
        self.ip_q = {}
        self.ip_map = {}
        self.last_ips = {}
        self.last_ips_time = {}
        self.bad_last_ips = {}
        self.bad_last_ips_time = {}
        for p in self.PROTOCOLS:
            self.ip_q[p] = []
            for _ in range(self.BUCKETS_NUMBER):
                self.ip_q[p].append([])
            self.ip_map[p] = {}
            self.last_ips[p] = []
            self.last_ips_time[p] = []
        

    def add_ip_with_priority(self, protocol, ipport, priority):
        if (len(self.ip_map[protocol]) > 0 and ipport in self.ip_map[protocol]) or len(ipport) < 10:
            return
        self.ip_map[protocol][ipport] = priority
        self.ip_q[protocol][priority].append(ipport)
    
    def add_ip(self, protocol, ipport):
        if (len(self.ip_map[protocol]) > 0 and ipport in self.ip_map[protocol]) or len(ipport) < 10:
            return
        self.ip_map[protocol][ipport] = self.NEW_IP_PRIORITY
        self.ip_q[protocol][self.NEW_IP_PRIORITY].append(ipport)
        
    def add_ip_bulk(self, protocol, ipports):
        for ipport in ipports:
            self.add_ip(protocol, ipport)

    def bad_ip(self, protocol, ipport):
        try:
            if ipport in self.ip_map[protocol].keys():
                priority = self.ip_map[protocol][ipport]
                new_priority = min(priority + 2, self.MAX_BAD_PRIORITY)
                self.ip_q[protocol][priority].remove(ipport)
                self.ip_q[protocol][new_priority].append(ipport)
                self.ip_map[protocol][ipport] = new_priority
        except:
            logger.exception("WTF bad_ip func")
    
    def del_priority(self, protocol, priority):
        try:
            for ipport in self.ip_q[protocol][priority]:
                del self.ip_map[protocol][ipport]
            self.ip_q[protocol][priority] = []
        except:
            logger.exception("WTF in del_proirity")
    
    def _get_n0th_ip(self, protocol, n):
        lens = [len(self.ip_q[protocol][i]) for i in range(self.BUCKETS_NUMBER)]
        if n >= sum(lens):
            return None
        count = 0
        for i in range(self.BUCKETS_NUMBER):
            if n < count + lens[i]:
                return self.ip_q[protocol][i][n-count]
            else:
                count += lens[i]
        return None
    
    def _get_good_proxy(self, protocol, change_priority=True):
        goods_count = sum([len(self.ip_q[protocol][p]) for p in range(self.MAX_GOOD_PRIORITY+1)])
        if goods_count < 10:
            return None
        try:
            ind = randint(0, goods_count - 1)
            while self._get_n0th_ip(protocol, ind) in self.last_ips[protocol]:
                while len(self.last_ips_time[protocol]) > 0 and time.time() - self.last_ips_time[protocol][0] > self.MIN_REUSE_TIME:
                    self.last_ips[protocol].pop(0)
                    self.last_ips_time[protocol].pop(0)            
                ind = randint(0, goods_count - 1)
            ip = self._get_n0th_ip(protocol, ind)
            priority = self.ip_map[protocol][ip]
            self.ip_q[protocol][priority].remove(ip)
            if change_priority:
                priority = max(priority - 1, 0)
            self.ip_q[protocol][priority].append(ip)
            self.ip_map[protocol][ip] = priority
            self.last_ips[protocol].append(ip)
            self.last_ips_time[protocol].append(time.time())
            return ip
        except:
            logger.exception("error in get_good_proxy")
        return None
    
    def get_bad_proxy(self, protocol):
        goods_count = sum([len(self.ip_q[protocol][p]) for p in range(self.MAX_GOOD_PRIORITY+1)])
        bads_count = sum([len(self.ip_q[protocol][p]) for p in range(self.MAX_GOOD_PRIORITY+1, self.MAX_BAD_PRIORITY+1)])
        if bads_count < 10:
            return None
        try:
            ind = goods_count + randint(0, bads_count - 1)
            while self._get_n0th_ip(protocol, ind) in self.last_ips[protocol]:
                while len(self.last_ips_time[protocol]) > 0 and time.time() - self.last_ips_time[protocol][0] > self.MIN_REUSE_TIME:
                    self.last_ips[protocol].pop(0)
                    self.last_ips_time[protocol].pop(0)            
                ind = goods_count + randint(0, bads_count - 1)
            ip = self._get_n0th_ip(protocol, ind)
            priority = self.ip_map[protocol][ip]
            self.ip_q[protocol][priority].remove(ip)
            priority = max(priority - 2, 0)
            self.ip_q[protocol][priority].append(ip)
            self.ip_map[protocol][ip] = priority
            self.last_ips[protocol].append(ip)
            self.last_ips_time[protocol].append(time.time())
            return ip
        except:
            logger.exception("WTF in get_bad func")
        return None
       
    
    def change_priority(self, protocol, src_p, dest_p):
        for ip in self.ip_q[protocol][src_p]:
            self.ip_map[protocol][ip] = dest_p
        self.ip_q[protocol][dest_p] = self.ip_q[protocol][dest_p] + self.ip_q[protocol][src_p]
        self.ip_q[protocol][src_p] = []
    
    def move_priority(self, protocol, src_p, dest_p, count):
        count = min(count, len(self.ip_q[protocol][src_p]))
        for ip in self.ip_q[protocol][src_p][:count]:
            self.ip_map[protocol][ip] = dest_p
        self.ip_q[protocol][dest_p] = self.ip_q[protocol][dest_p] + self.ip_q[protocol][src_p][:count]
        self.ip_q[protocol][src_p] = self.ip_q[protocol][src_p][count:]
    
    def get_stat(self, protocol):
        goods_count = sum([len(self.ip_q[protocol][p]) for p in range(self.MAX_GOOD_PRIORITY+1)])
        bads_count = sum([len(self.ip_q[protocol][p]) for p in range(self.MAX_GOOD_PRIORITY+1, self.BUCKETS_NUMBER)])
        bins = [len(self.ip_q[protocol][p]) for p in range(len(self.ip_q[protocol]))]
        return {"prot": protocol, "# ip_q": goods_count+bads_count, "# last_ips": len(self.last_ips[protocol]), "# goods": goods_count, "ips: ": bins}
    
    def save_to_file(self, file_name='./proxies0'):
        for protocol in self.PROTOCOLS:
            with open(f"{file_name}_{protocol}.txt", 'w') as f:
                for p in range(len(self.ip_q[protocol])):
                    for ip in self.ip_q[protocol][p]:
                        f.write(f"{p},{ip}\n")
    
    def _add_file_proxies(self):
        try:
            for protocol in self.PROTOCOLS:
                file_name = f"./proxies_{protocol}.txt"
                if os.path.isfile(file_name):
                    f = open(file_name, "r")
                    l = f.readline()
                    ps = []
                    while l:
                        ps.append(l.replace("\n", "").split(","))
                        l = f.readline()
                    for p in ps:
                        self.add_ip_with_priority(protocol, p[1], int(p[0]))
        except:
            logger.exception("couldnt read proxy file")

            
    def get_proxy(self, protocol):
        return self._get_good_proxy(protocol)


proxy_provider = ProxyProvider()
app = Sanic("proxy_server")


@app.route('/get_proxy/<protocol>')
async def get(request, protocol):
    if protocol not in proxy_provider.PROTOCOLS:
        return json({"result": "protocol not found"})
    try:
        proxy = proxy_provider.get_proxy(protocol)
        if proxy:
            return json({"proxy": proxy})
        else:
            return None
    except:
        logger.exception("WTF in get_proxy")
        return json({"proxy": None})

@app.route('/get_bad_proxy/<protocol>')
async def get_bad_proxy(request, protocol):
    if protocol not in proxy_provider.PROTOCOLS:
        return json({"result": "protocol not found"})
    try:
        proxy = {"proxy": proxy_provider.get_bad_proxy(protocol)}
        if proxy:
            return json({"proxy": proxy})
        else:
            return None
    except:
        logger.exception("WTF in get_bad_proxy")
        return json({"proxy": None})

@app.route('/bad_ip/<protocol>/<ipport>')
async def bad_ip(request, protocol, ipport):
    if protocol not in proxy_provider.PROTOCOLS:
        return json({"result": "protocol not found"})
    try:
        proxy_provider.bad_ip(protocol, ipport)
        return json({"result": "done"})
    except:
        logger.exception("WTF in bad_ip")
        return json({"result": "failed"})

@app.route('/add_ip/<protocol>/<ipport>')
async def add_ip(request, protocol, ipport):
    if protocol not in proxy_provider.PROTOCOLS:
        return json({"result": "protocol not found"})
    try:
        proxy_provider.add_ip(protocol, ipport)
        return json({"result": "done"})
    except:
        logger.exception("WTF in add_ip")
        return json({"result": "failed"})

@app.post('/add_ip_bulk/<protocol>')
async def add_ip_bulk(request, protocol):
    if protocol not in proxy_provider.PROTOCOLS:
        return json({"result": "protocol not found"})
    try:
        proxy_provider.add_ip_bulk(protocol, request.json)
        return json({"result": "done"})
    except:
        logger.exception("WTF in add_ip_bulk")
        return json({"result": "failed"})

@app.route('/save')
async def save(request):
    try:
        proxy_provider.save_to_file()
        return json({"result": "done"})
    except:
        logger.exception("WTF in save")
        return json({"result": "failed"})

@app.route('/stat/<protocol>')
async def stat(request, protocol):
    if protocol not in proxy_provider.PROTOCOLS:
        return json({"result": "protocol not found"})
    try:
        return json(proxy_provider.get_stat(protocol))
    except:
        logger.exception("WTF in stat")
        return json({"result": "failed"})

@app.route('/chng_p/<protocol>/<src_p>/<dest_p>')
async def chng_p(request, protocol, src_p, dest_p):
    if protocol not in proxy_provider.PROTOCOLS:
        return json({"result": "protocol not found"})
    try:
        proxy_provider.change_priority(protocol, int(src_p), int(dest_p))
        return json({"result": "done"})
    except:
        logger.exception("WTF in chng_p")
        return json({"result": "failed"})
@app.route('/move_p/<protocol>/<src_p>/<dest_p>/<count>')
async def move_priority(request, protocol, src_p, dest_p, count):
    if protocol not in proxy_provider.PROTOCOLS:
        return json({"result": "protocol not found"})
    try:
        proxy_provider.move_priority(protocol, int(src_p), int(dest_p), int(count))
        return json({"result": "done"})
    except:
        logger.exception("WTF in move_p")
        return json({"result": "failed"})

    
@app.route('/del_p/<protocol>/<priority>')
async def del_p(request, protocol, priority):
    if protocol not in proxy_provider.PROTOCOLS:
        return json({"result": "protocol not found"})
    try:
        proxy_provider.del_priority(protocol, int(priority))
        return json({"result": "done"})
    except:
        logger.exception("WTF in del_p")
        return json({"result": "failed"})
    
if __name__ == '__main__':
    def setup_logger(file_name):
            logger.remove()
            logger.add(f"./logs/{file_name}-debug.log", format="{time} {level} {message}", level="DEBUG", enqueue=True)
            logger.add(f"./logs/{file_name}-info.log", format="{time} {level} {message}", level="INFO", enqueue=True, backtrace=True)
            logger.add(f"./logs/{file_name}-error.log", format="{time} {level} {message}", level="ERROR", enqueue=True, backtrace=True, diagnose=True)
    setup_logger("proxy_server")
    time.sleep(10)
    proxy_provider._add_file_proxies()
    app.run(host='0.0.0.0', port=8008)