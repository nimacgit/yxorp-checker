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
        self.ip_q = {}
        self.ip_map = {}
        self.last_ips = {}
        self.last_ips_time = {}
        self.bad_last_ips = {}
        self.bad_last_ips_time = {}
        for p in self.PROTOCOLS:
            self.ip_q[p] = []
            self.ip_map[p] = {}
            self.last_ips[p] = []
            self.last_ips_time[p] = []
            self.bad_last_ips[p] = []
            self.bad_last_ips_time[p] = []
        self.readed_file = False
        self.last_pubproxy_time = time.time()
        self.last_scylla_time = time.time()
        self.last_save_time = time.time()
        self.last_proxy_url_time = time.time()
        self.is_firt_time = True
        self.min_reuse_time = 30
        self.max_ip_priority = 4
        self.new_ip_priority = 3

    def add_ip_with_priority(self, protocol, ipport, priority):
        if (len(self.ip_map[protocol]) > 0 and ip in self.ip_map[protocol]) or len(ipport) < 10:
            return
        self.ip_map[protocol][ipport] = priority
        heapq.heappush(self.ip_q[protocol], (priority, ipport))
    
    def add_ip(self, protocol, ipport):
        if (len(self.ip_map[protocol]) > 0 and ip in self.ip_map[protocol]) or len(ipport) < 10:
            return
        self.ip_map[protocol][ipport] = self.new_ip_priority
        heapq.heappush(self.ip_q[protocol], (self.new_ip_priority, ipport))
        
    def add_ip_bulk(self, protocol, ipports):
        for ipport in ipports:
            self.add_ip(protocol, ipport)

    def bad_ip(self, protocol, ip):
        try:
            if ip in self.ip_map[protocol].keys():
                for i in range(len(self.ip_q[protocol])):
                    if len(self.ip_q[protocol][i]) < 2:
                        logger.info(f"WARNING! {i} --- {self.ip_q[protocol][i]}")
                    if self.ip_q[protocol][i][1] == ip:
                        self.ip_q[protocol][i] = (min(self.ip_q[protocol][i][0] + 2, self.max_ip_priority), self.ip_q[protocol][i][1])
                v = self.ip_map[protocol][ip]
                self.ip_map[protocol][ip] = min(v + 2, self.max_ip_priority)
                heapq.heapify(self.ip_q[protocol])
        except:
            logger.exception("WTF bad_ip func")
    
    def del_priority(self, protocol, priority):
        nodes = []
        try:
            while len(self.ip_q[protocol]) > 0:
                p = heapq.heappop(self.ip_q[protocol])
                if p[0] != priority:
                    nodes.append(p)
                else:
                    del self.ip_map[protocol][p[1]]
        except:
            logger.exception("WTF in del_proirity")
        for p in nodes:
            self.ip_q[protocol].append(p)
        heapq.heapify(self.ip_q[protocol])

    def _get_good_proxy(self, protocol, change_priority=True):
        if len(self.ip_q[protocol]) < 10:
            return
        min_val = self.ip_q[protocol][0][0]
        nodes = []
        try:
            while len(self.ip_q[protocol]) > 0 and self.ip_q[protocol][0][0] <= min_val+3:
                nodes.append(heapq.heappop(self.ip_q[protocol]))
            retry = True
            while retry:
                while len(self.last_ips_time[protocol]) > 0 and time.time() - self.last_ips_time[protocol][0] > self.min_reuse_time:
                    self.last_ips[protocol].pop(0)
                    self.last_ips_time[protocol].pop(0)
                ind = randint(0, len(nodes) - 1)
                if len(self.last_ips[protocol]) + len(self.bad_last_ips[protocol]) + 5 >= len(nodes):
                    time.sleep(3)
                else:
                    retry = False
            while nodes[ind][1] in self.last_ips[protocol] or nodes[ind][1] in self.bad_last_ips[protocol]:
                ind = randint(0, len(nodes) - 1)
            if change_priority:
                nodes[ind] = (max(nodes[ind][0] - 1, 0), nodes[ind][1])
            else:
                nodes[ind] = (nodes[ind][0], nodes[ind][1])
            self.ip_map[protocol][nodes[ind][1]] = nodes[ind][0]
            self.last_ips[protocol].append(nodes[ind][1])
            self.last_ips_time[protocol].append(time.time())
        except:
            logger.exception("error in get_good_proxy")
        for i in range(len(nodes)):
            heapq.heappush(self.ip_q[protocol], nodes[i])
        return nodes[ind][1]
    
    def get_bad_proxy(self, protocol):
        if len(self.ip_q[protocol]) < 10:
            return
        min_val = self.ip_q[protocol][0][0]
        nodes = []
        min_val_ind = 0
        try:
            while len(self.ip_q[protocol]) > 0 and self.ip_q[protocol][0][0] < 8:
                if self.ip_q[protocol][0][0] <= min_val+3:
                    min_val_ind = min_val_ind + 1
                nodes.append(heapq.heappop(self.ip_q[protocol]))
            if len(nodes) - min_val_ind < 5:
                for i in range(len(nodes)):
                    self.ip_q[protocol].append(nodes[i])
                heapq.heapify(self.ip_q[protocol])
                return
            retry = True
            while retry:
                while len(self.bad_last_ips_time[protocol]) > 0 and time.time() - self.bad_last_ips_time[protocol][0] > self.min_reuse_time:
                    self.bad_last_ips[protocol].pop(0)
                    self.bad_last_ips_time[protocol].pop(0)
                ind = randint(min_val_ind, len(nodes) - 1)
                if len(self.last_ips[protocol]) + len(self.bad_last_ips[protocol]) + 5 >= len(nodes):
                    time.sleep(3)
                else:
                    retry = False
            while nodes[ind][1] in self.bad_last_ips[protocol] or nodes[ind][1] in self.last_ips[protocol]:
                ind = randint(min_val_ind, len(nodes) - 2)
            nodes[ind] = (max(nodes[ind][0] - 2, 0), nodes[ind][1])
            self.ip_map[protocol][nodes[ind][1]] = nodes[ind][0]
            self.bad_last_ips[protocol].append(nodes[ind][1])
            self.bad_last_ips_time[protocol].append(time.time())
        except:
            logger.exception("WTF in get_bad func")
        for i in range(len(nodes)):
            self.ip_q[protocol].append(nodes[i])
        heapq.heapify(self.ip_q[protocol])
        return nodes[ind][1]

    def change_priority(self, protocol, src_p, dest_p):
        for i in range(len(self.ip_q[protocol])):
            if self.ip_q[protocol][i][0] == src_p:
                self.ip_map[protocol][self.ip_q[protocol][i][1]] = dest_p
                self.ip_q[protocol][i] = (dest_p, self.ip_q[protocol][i][1])
        heapq.heapify(self.ip_q[protocol])
        
    def get_stat(self, protocol):
        if protocol not in self.PROTOCOLS:
            return {"result": "protocol not found"}
        if len(self.ip_q[protocol]) > 0:
            min_val = self.ip_q[protocol][0][0]
        else:
            min_val = 6
        cnt = 0
        bins = buckets = [0] * 16
        for p,ip in self.ip_q[protocol]:
            if p <= min_val+3:
                cnt += 1
            bins[p] += 1
        return {"prot": protocol, "# ip_q": len(self.ip_q[protocol]), "# last_ips": len(self.last_ips[protocol]), "# goods": cnt, " bad_last": len(self.bad_last_ips[protocol]), "ips: ": bins}
    
    def save_to_file(self, file_name='./proxies0'):
        for protocol in self.PROTOCOLS:
            with open(f"{file_name}_{protocol}.txt", 'w') as f:
                for p in self.ip_q[protocol]:
                    f.write(f"{p[0]},{p[1]}\n")
    
    def _add_file_proxies(self):
        try:
            self.readed_file = True
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
time.sleep(10)
proxy_provider._add_file_proxies()
app = Sanic()


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
        return {"result": "protocol not found"}
    try:
        proxy = json({"proxy": proxy_provider.get_bad_proxy(protocol)})
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
async def add_ip(request, ipport):
    if protocol not in proxy_provider.PROTOCOLS:
        return json({"result": "protocol not found"})
    try:
        proxy_provider.add_ip(protocol, ipport)
        return json({"result": "done"})
    except:
        logger.exception("WTF in add_ip")
        return json({"result": "failed"})

@app.post('/add_ip_bulk/<protocol>')
async def add_ip_bulk(request):
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
    
    app.run(host='0.0.0.0', port=8008)