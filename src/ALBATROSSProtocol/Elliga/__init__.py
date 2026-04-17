'''
from .curve25519 import *
from .elligator import *

u = GF(9)
p = 2**255 - 19
v = 14781619447589544791020593568409986887264606134616475288964881837755586237401

is_negative = v > (p - 1) // 2
print(is_negative)

r = rev_map(u, v_is_negative)
'''
