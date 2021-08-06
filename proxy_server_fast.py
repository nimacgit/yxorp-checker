from sanic.response import json
from loguru import logger
from sanic import Sanic
import asyncio
import time
import os


class Node:
    def __init__(self, value=None, next_node=None, prev_node=None):
        self.value = value
        self.next_node = next_node
        self.prev_node = prev_node

class LinkedList:
    def __init__(self):
        self.head = None
        self.tail = None
        self.size = 0

    def append_node(self, node):
        node.prev_node = None
        node.next_node = None
        if self.size == 0:
            self.head = node
        elif self.size == 1:
            self.tail = node
            self.head.next_node = node
            self.tail.prev_node = self.head
        else:
            self.tail.next_node = node
            node.prev_node = self.tail
            self.tail = node
        self.size += 1
        return node

    def append(self, value):
        node = Node(value, None, None)
        self.append_node(node)
        return node

    def push_front_node(self, node):
        node.prev_node = None
        node.next_node = None
        if self.size == 0:
            self.head = node
        elif self.size == 1:
            self.tail = self.head
            self.head = node
            self.tail.prev_node = self.head
            self.head.next_node = self.tail
        else:
            self.head.prev_node = node
            node.next_node = self.head
            self.head = node
        self.size += 1
        return node

    def push_front(self, value):
        node = Node(value, None, None)
        self.push_front_node(node)
        return node

    def first(self):
        return self.head
    
    def pop(self):
        if self.size == 0:
            return

        node = self.head
        val = node.value
        self.size -= 1

        if self.size == 0:
            self.head = None
            self.tail = None
        elif self.size == 1:
            self.head = self.tail
            self.tail = None            
        else:
            self.head.next_node.prev_node = None
            self.head = self.head.next_node
        return node
        
    def delete_node(self, node):
        self.size -= 1
        if self.size == 0:
            self.head = None
            self.tail = None
            return
        if node == self.head:
            v = self.pop()
            del v
            return
        elif node == self.tail:
            self.tail = self.tail.prev_node
            self.tail.next_node = None
        else:
            node.prev_node.next_node = node.next_node
            node.next_node.prev_node = node.prev_node
        del node
        

class Proxy:
    def __init__(self, ipport, priority, node):
        self.ipport = ipport
        self.priority = priority
        self.node = node
        self.last_used = None

    def get_ipport_with_priority(self):
        return [self.ipport, self.priority]
        
    
    
class ProxyQueueManager:
    def __init__(self, protocol, buckets=15):
        self.BUCKETS_NUMBER = buckets
        self.PROTOCOL = protocol
        self.BUCKETS_NUMBER = 15
        self.MIN_REUSE_TIME = 30
        self.MAX_GOOD_PRIORITY = 3
        self.MAX_BAD_PRIORITY = 7
        self.QUEUE_MAX_SIZE = 500000
        self.proxy_meta = {}
        self.buckets = []
        for _ in range(self.BUCKETS_NUMBER):
            self.buckets.append(LinkedList())

    def add_ip_with_priority(self, ipport, priority):
        if self.proxy_meta.get(ipport, None) is not None:
            return
        node = self.buckets[priority].append(ipport)
        self.proxy_meta[ipport] = Proxy(ipport, priority, node)
        
    
    def get_good_proxy(self):
        for i in range(self.MAX_GOOD_PRIORITY + 1):
            bucket = self.buckets[i]
            if bucket.size > 0:
                first = self.buckets[i].first()
                proxy = self.proxy_meta[first.value]
                if proxy.last_used is None or time.time() - proxy.last_used > self.MIN_REUSE_TIME:
                    self.buckets[i].pop()
                    self.buckets[max(i-1, 0)].append_node(first)
                    proxy.priority = max(i-1, 0)
                    proxy.last_used = time.time()
                    return first.value

    
    def bad_proxy(self, ipport):
        proxy = self.proxy_meta.get(ipport, None)
        if proxy:
            self.buckets[proxy.priority].delete_node(proxy.node)
            proxy.priority = min(proxy.priority + 2, self.MAX_GOOD_PRIORITY + 1)
            proxy.last_used = time.time()
            self.buckets[proxy.priority].append_node(proxy.node)
    
    def delete_priority(self, priority):
        while self.buckets[priority].size > 0:
            node = self.buckets[priority].pop()
            del self.proxy_meta[node.value]
                
    def change_priority(self, src_p, dest_p, count=-1):
        while self.buckets[src_p].size > 0 and count != 0:
            node = self.buckets[src_p].pop()
            self.proxy_meta[node.value].priority = dest_p
            if self.proxy_meta[node.value].last_used is None or time.time() - self.proxy_meta[node.value].last_used > self.MIN_REUSE_TIME:
                self.buckets[dest_p].push_front_node(node)
            else:
                self.buckets[dest_p].append_node(node)
            count -= 1
            
    def get_stat(self):
        goods = sum([self.buckets[p].size for p in range(self.MAX_GOOD_PRIORITY+1)])
        bads = sum([self.buckets[p].size for p in range(self.MAX_GOOD_PRIORITY+1, self.BUCKETS_NUMBER)])
        bins = [self.buckets[p].size for p in range(self.BUCKETS_NUMBER)]
        return goods, bads, bins

    def get_ipports(self):
        return [self.proxy_meta[k].get_ipport_with_priority() for k in self.proxy_meta.keys()]

class ProxyProvider:
    PROTOCOLS = ["https", "http", "socks5"]

    def __init__(self):
        self.managers = {}
        self.NEW_IP_PRIORITY = 3
        self.usage_list = LinkedList()
        for p in self.PROTOCOLS:
            self.managers[p] = ProxyQueueManager(protocol=p)

    def add_ip_with_priority(self, protocol, ipport, priority):
        if len(ipport) < 10:
            return
        self.managers[protocol].add_ip_with_priority(ipport, priority)

    def add_ip_bulk(self, protocol, ipports):
        for ipport in ipports:
            self.add_ip_with_priority(protocol, ipport, priority=self.NEW_IP_PRIORITY)

    def get_proxy(self, protocol):
        try:
            self.usage_list.append(time.time())
            while self.usage_list.size > 0 and time.time() - self.usage_list.first().value > 30:
                tmp = self.usage_list.pop()
                del tmp
            return self.managers[protocol].get_good_proxy()
        except:
            logger.exception("WTF bad_proxy func")

    def bad_proxy(self, protocol, ipport):
        try:
            self.managers[protocol].bad_proxy(ipport)
        except:
            logger.exception("WTF bad_proxy func")
    
    def delete_priority(self, protocol, priority):
        try:
            self.managers[protocol].delete_priority(priority)
        except:
            logger.exception("WTF in del_proirity")

    def change_priority(self, protocol, src_p, dest_p):
        self.managers[protocol].change_priority(src_p, dest_p)
    
    def move_priority(self, protocol, src_p, dest_p, count):
        self.managers[protocol].change_priority(src_p, dest_p, count)
    
    def get_stat(self, protocol):
        goods_count, bads_count, bins = self.managers[protocol].get_stat()
        return {"prot": protocol, "# ip_q": goods_count+bads_count, "# last_ips": self.usage_list.size, "# goods": goods_count, "ips: ": bins}
    
    def save_to_file(self, file_name='./proxies0'):
        for protocol in self.PROTOCOLS:
            with open(f"{file_name}_{protocol}.txt", 'w') as f:
                for ip, p in self.managers[protocol].get_ipport_with_priority():
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

@app.route('/bad_proxy/<protocol>/<ipport>')
async def bad_proxy(request, protocol, ipport):
    if protocol not in proxy_provider.PROTOCOLS:
        return json({"result": "protocol not found"})
    try:
        proxy_provider.bad_proxy(protocol, ipport)
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
        proxy_provider.delete_priority(protocol, int(priority))
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
    app.run(host='0.0.0.0', port=8008, debug=False, access_log=False)