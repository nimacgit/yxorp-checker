from nimac.proxy.proxy_server_fast import ProxyProvider, Node
import tracemalloc
from tqdm import trange
import random
import time

tracemalloc.start()

pp = ProxyProvider()
pp.managers["https"].MIN_REUSE_TIME = 2
for i in range(4):
    await pp.add_ip_with_priority("https", f"000000000000000{i}", i%4)

# await pp.add_ip_bulk("https", [f"000000000000000{i}" for i in range(4000, 5000)])
print(pp.get_stat("https"))
# await pp._add_file_proxies("./nimac/proxy")
# pp.save_to_file(file_name='./proxies0')
# print(pp.get_stat("https"))

# await pp.delete_priority("https", 1)
# await pp.delete_priority("https", 2)
# await pp.delete_priority("https", 3)
# await pp.delete_priority("https", 4)
# await pp.change_priority("https", 0, 1)
# await pp.move_priority("https", 1, 2, 100)
# await pp.move_priority("https", 1, 0, 100)
# await pp.move_priority("https", 1, 3, 100)

pp.managers["https"].print_state()
p = await pp.get_proxy("https")
await pp.bad_proxy("https", p["proxy"])
# await pp.bad_proxy("https", p["proxy"])
pp.managers["https"].print_state()

# for _ in range(4):
#     for _ in trange(10):
#         p = await pp.get_proxy("https")
#         if p and random.randint(0, 100) < 30:
#             p = p["proxy"]
#             await pp.bad_proxy("https", p)
# #             await pp.bad_proxy("https", p)

#     pp.managers["https"].print_state()
    
# #     await pp.change_priority("https", random.randint(0, 3), random.randint(0, 3))
# #     await pp.move_priority("https", 4, random.randint(0, 3), 100)
# #     await pp.move_priority("https", 4, random.randint(0, 3), 100)

#     time.sleep(2)
