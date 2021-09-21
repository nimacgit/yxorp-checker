from sanic.response import json
from threading import Lock
from loguru import logger
from sanic import Sanic
import asyncio
import time
import copy
import os
import re

class Node:
    def __init__(self, value=None, next_node=None, prev_node=None):
        self.value = value
        self.next_node = next_node
        self.prev_node = prev_node

    def clone(self):
        node = Node()
        node.value = self.value
        node.next_node = self.next_node
        node.prev_node = self.prev_node
        return node

class LinkedList:
    def __init__(self):
        self.head = None
        self.tail = None
        self.size = 0
        self.lock = Lock()

    async def append_node(self, node):
        self.lock.acquire()
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
        self.lock.release()
        return node

    async def append(self, value):
        node = Node(value, None, None)
        await self.append_node(node)
        return node

    async def push_front_node(self, node):
        self.lock.acquire()
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
        self.lock.release()
        return node

    async def push_front(self, value):
        node = Node(value, None, None)
        await self.push_front_node(node)
        return node

    def first(self):
        return self.head
    
    async def pop(self):
        self.lock.acquire()
        if self.size == 0:
            self.lock.release()
            return
        node = self.head
        val = node.value
        self.size -= 1
        if self.size < 0:
            logger.exception("-1 -1 -1 pop")
            raise
        if self.size == 0:
            self.head = None
            self.tail = None
        elif self.size == 1:
            self.head = self.tail
            self.head.prev_node = None
            self.tail = None            
        else:
            self.head.next_node.prev_node = None
            self.head = self.head.next_node
        self.lock.release()
        return node
        
    def get_nodes_stat(self):
        res = []
        node = self.head
        while node is not None:
            res.append(node)
            node = node.next_node
        return {"nodes": res, "tail": self.tail, "head": self.head}

    def print_state(self):
        node = self.head
        while node is not None:
            print(node.value, end=" --> ")
            node = node.next_node
        print()

class Proxy:
    def __init__(self, ipport, priority, node, last_used=None):
        self.ipport = ipport
        self.priority = priority
        self.node = node
        self.last_used = last_used

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
        self.lock = Lock()
        for _ in range(self.BUCKETS_NUMBER):
            self.buckets.append(LinkedList())

    async def add_ip_with_priority(self, ipport, priority):
        self.lock.acquire()
        if self.proxy_meta.get(ipport, None) is not None:
            self.lock.release()
            return
        node = await self.buckets[priority].append(ipport)
        self.proxy_meta[ipport] = Proxy(ipport, priority, node)
        self.lock.release()
        
    
    async def get_good_proxy(self):
        p = 0
        while p <= self.MAX_GOOD_PRIORITY:
            bucket = self.buckets[p]
            self.lock.acquire()
            if bucket.size > 0:
                first = bucket.first()
                proxy = self.proxy_meta[first.value]
                if first == proxy.node:
                    if proxy.last_used is None or time.time() - proxy.last_used > self.MIN_REUSE_TIME:
                        node = await bucket.pop()
                        proxy.priority = max(proxy.priority-1, 0)
                        await self.buckets[proxy.priority].append_node(node)
                        proxy.last_used = time.time()
                        self.lock.release()
                        return first.value
                else:
#                     bucket.size += 1
                    node = await bucket.pop()
                    del node
                    p -= 1
            p += 1
            self.lock.release()
    
    async def bad_proxy(self, ipport):
        self.lock.acquire()
        proxy = self.proxy_meta.get(ipport, None)
        if proxy:
#             await self.buckets[proxy.priority].delete_node(proxy.node)
#             self.buckets[proxy.priority].size -= 1
            proxy.node = proxy.node.clone()
#             proxy.node = Node(proxy.node.value, proxy.node.next_node, proxy.node.prev_node)
            proxy.priority = min(proxy.priority + 2, self.MAX_GOOD_PRIORITY + 1)
            proxy.last_used = time.time()
            await self.buckets[proxy.priority].append_node(proxy.node)
        self.lock.release()
    
    async def delete_priority(self, priority):
        self.lock.acquire()
        while self.buckets[priority].size > 0:
            node = await self.buckets[priority].pop()
            if self.proxy_meta[node.value].node == node:
                del self.proxy_meta[node.value]
            else:
#                 self.buckets[priority].size += 1
                del node
        self.lock.release()

    async def change_priority(self, src_p, dest_p, count=-1):
        if src_p == dest_p:
            return
        self.lock.acquire()
        while self.buckets[src_p].size > 0 and count != 0:
            node = await self.buckets[src_p].pop()
            proxy = self.proxy_meta[node.value]
            if proxy.node == node:
                proxy.priority = dest_p
                if proxy.last_used is None or time.time() - proxy.last_used > self.MIN_REUSE_TIME:
                    await self.buckets[proxy.priority].push_front_node(node)
                else:
                    await self.buckets[proxy.priority].append_node(node)
                count -= 1
            else:
#                 self.buckets[src_p].size += 1
                del node
        self.lock.release()

    def get_stat(self):
        goods = sum([self.buckets[p].size for p in range(self.MAX_GOOD_PRIORITY+1)])
        bads = sum([self.buckets[p].size for p in range(self.MAX_GOOD_PRIORITY+1, self.BUCKETS_NUMBER)])
        bins = [self.buckets[p].size for p in range(self.BUCKETS_NUMBER)]
        return goods, bads, bins

    def get_ipports(self):
        return [self.proxy_meta[k].get_ipport_with_priority() for k in self.proxy_meta.keys()]
    
    def print_state(self):
        for ind, b in enumerate(self.buckets):
            stat = b.get_nodes_stat()
            nodes = stat["nodes"]
            print(f"{ind} size: {b.size}", end=": ")
            for n in nodes:
                print(f"{n.value} - {n} - {self.proxy_meta[n.value].priority}", end=" --> ")
            print()
            if stat["head"]:
                print(f"head: {stat['head'].value} - {stat['head']} - {self.proxy_meta[stat['head'].value].priority} - p: {stat['head'].prev_node} - n: {stat['head'].next_node}")
            if stat["tail"]:
                print(f"tail: {stat['tail'].value} - {stat['tail']} - {self.proxy_meta[stat['tail'].value].priority} - p: {stat['tail'].prev_node} - n: {stat['tail'].next_node}")
        print()

class ProxyProvider:
    PROTOCOLS = ["https", "http", "socks5"]
    IPPORT_REGEX = "^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5]):([0-9]{1,4}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5])$"

    def __init__(self):
        self.managers = {}
        self.NEW_IP_PRIORITY = 3
        self.usage_list = LinkedList()
        for p in self.PROTOCOLS:
            self.managers[p] = ProxyQueueManager(protocol=p)

    async def add_ip_with_priority(self, protocol, ipport, priority):
        if len(ipport) < 10 and not re.match(IPPORT_REGEX, ipport):
            return
        await self.managers[protocol].add_ip_with_priority(ipport, priority)

    async def add_ip_bulk(self, protocol, ipports):
        for ipport in ipports:
            await self.add_ip_with_priority(protocol, ipport, priority=self.NEW_IP_PRIORITY)

    async def get_proxy(self, protocol):
        if protocol not in self.PROTOCOLS:
            return {"result": "protocol not found"}
        try:
            await self.usage_list.append(time.time())
            while self.usage_list.size > 0 and time.time() - self.usage_list.first().value > 30:
                tmp = await self.usage_list.pop()
                del tmp
            res = await self.managers[protocol].get_good_proxy()
            return {"proxy": res}
        except:
            logger.exception("WTF get_proxy func")
            return {"proxy": None}

    async def bad_proxy(self, protocol, ipport):
        if protocol not in self.PROTOCOLS:
            return {"result": "protocol not found"}
        try:
            await self.managers[protocol].bad_proxy(ipport)
            return {"result": "success"}
        except:
            logger.exception("WTF bad_proxy func")
            return {"result": "failed"}
        
    async def delete_priority(self, protocol, priority):
        try:
            await self.managers[protocol].delete_priority(priority)
        except:
            logger.exception("WTF in del_proirity")

    async def change_priority(self, protocol, src_p, dest_p):
        await self.managers[protocol].change_priority(src_p, dest_p)
    
    async def move_priority(self, protocol, src_p, dest_p, count):
        await self.managers[protocol].change_priority(src_p, dest_p, count)
    
    def get_stat(self, protocol):
        goods_count, bads_count, bins = self.managers[protocol].get_stat()
        return {"prot": protocol, "# ip_q": goods_count+bads_count, "# last_ips": self.usage_list.size, "# goods": goods_count, "ips: ": bins}
    
    def save_to_file(self, file_name='./proxies0'):
        for protocol in self.PROTOCOLS:
            with open(f"{file_name}_{protocol}.txt", 'w') as f:
                for ip, p in self.managers[protocol].get_ipports():
                    f.write(f"{p},{ip}\n")
    
    async def _load_data(self, path="."):
        try:
            for protocol in self.PROTOCOLS:
                file_name = f"{path}/proxies_{protocol}.txt"
                if os.path.isfile(file_name):
                    f = open(file_name, "r")
                    l = f.readline()
                    ps = []
                    while l:
                        ps.append(l.replace("\n", "").split(","))
                        l = f.readline()
                    for p in ps:
                        await self.add_ip_with_priority(protocol, p[1], int(p[0]))
        except:
            logger.exception("couldnt read proxy file")
    
    



proxy_provider = ProxyProvider()
app = Sanic("proxy_server")

@app.route('/get_proxy/<protocol>')
async def get(request, protocol):
    try:
        return json(await proxy_provider.get_proxy(protocol))
    except:
        logger.exception("WTF in get_proxy")
        return json({"proxy": None})

@app.route('/bad_proxy/<protocol>/<ipport>')
async def bad_proxy(request, protocol, ipport):
    
    try:
        return json(await proxy_provider.bad_proxy(protocol, ipport))
    except:
        logger.exception("WTF in bad_ip")
        return json({"result": "failed"})

@app.route('/add_ip/<protocol>/<ipport>')
async def add_ip(request, protocol, ipport):
    if protocol not in proxy_provider.PROTOCOLS:
        return json({"result": "protocol not found"})
    try:
        await proxy_provider.add_ip(protocol, ipport)
        return json({"result": "done"})
    except:
        logger.exception("WTF in add_ip")
        return json({"result": "failed"})

@app.post('/add_ip_bulk/<protocol>')
async def add_ip_bulk(request, protocol):
    if protocol not in proxy_provider.PROTOCOLS:
        return json({"result": "protocol not found"})
    try:
        await proxy_provider.add_ip_bulk(protocol, request.json)
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
        await proxy_provider.change_priority(protocol, int(src_p), int(dest_p))
        return json({"result": "done"})
    except:
        logger.exception("WTF in chng_p")
        return json({"result": "failed"})

@app.route('/move_p/<protocol>/<src_p>/<dest_p>/<count>')
async def move_priority(request, protocol, src_p, dest_p, count):
    if protocol not in proxy_provider.PROTOCOLS:
        return json({"result": "protocol not found"})
    try:
        await proxy_provider.move_priority(protocol, int(src_p), int(dest_p), int(count))
        return json({"result": "done"})
    except:
        logger.exception("WTF in move_p")
        return json({"result": "failed"})

@app.route('/del_p/<protocol>/<priority>')
async def del_p(request, protocol, priority):
    if protocol not in proxy_provider.PROTOCOLS:
        return json({"result": "protocol not found"})
    try:
        await proxy_provider.delete_priority(protocol, int(priority))
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
    time.sleep(1)
    asyncio.run(proxy_provider._load_data())
    app.run(host='0.0.0.0', port=8008, debug=False, access_log=False, workers=1, auto_reload=False)
#     asyncio.gather(app.create_server(host='0.0.0.0', port=8008, debug=False, access_log=False))
#     loop = asyncio.get_event_loop()
#     task = asyncio.ensure_future(server)
#     loop.run_forever()