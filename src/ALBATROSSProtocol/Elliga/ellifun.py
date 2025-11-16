from .curve25519 import *
from .elligator import *
import random
from random import randrange

def map_to_curve(random):
    y_sign = random // 2**255
    r = random % 2**255
    u, _ = dir_map(GF(r))  # Elligator direct map
    x, y, z = to_edwards(u)  # Convert to Edwards form
    if x.to_num() % 2 != y_sign:
        x = -x
    x, y, z = Ed.scalarmult((x, y, z), 8)  # Multiply by cofactor
    z = z.invert()
    y = y * z
    x = x * z
    x_sign = x.to_num() % 2
    point = y.to_num() + x_sign * 2**255
    return point
from ALBATROSSProtocol.Elliga.elligator import rev_map
from ALBATROSSProtocol.Elliga.core import GF

# Example point u and v_sign

'''
for i in range(1,30):
    try:
        u = GF(i)  # Replace with actual u-coordinate
        v_is_negative = False  # or True depending on the sign of v

        # Recover the representative
        r = rev_map(u, v_is_negative)

        if r is not None:
            print("Recovered representative:", r.to_num())
        else:
            print("This point cannot be mapped back via Elligator.")
    except:
        pass
'''
def CurvetoNumber(point):
    u=GF(point.x)
    v=int(point.y)+19<2**254 #This depends on the chosen curve.
    try:
        x=rev_map(u,v)
        if x is not None:
            return x.to_num()
        else:
            return random.randint(0, 1000)
    except:
        return random.randint(0,1000)