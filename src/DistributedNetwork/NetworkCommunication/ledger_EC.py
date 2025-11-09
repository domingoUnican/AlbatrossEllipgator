from ALBATROSSProtocol.Proofs.LDEI import LDEI
from ALBATROSSProtocol.Proofs.DLEQ import DLEQ
from ecpy.curves import Curve, Point

class Ledger_EC:
    def __init__(self, n, q, h, pk=None):
        """
        Ledger using Elliptic Curves
        args:
        n: Number of participants
        q: Size of the curve
        h: Point generator of the curve
        """
        
        self.n = n
        self.q = q
        self.t = round(n // 3) 
        self.l = n - (2 * self.t)  
        self.h = h
        self.pk = [Curve.get_curve('Curve25519')._domain["generator"]] * n
        self.P = []
        self.alpha = []
        self.r = 0  
        self.encrypted_fragments = []  
        self.revealed_fragments = [0] * n  
        self.ld = None  
        self.dl: list[DLEQ] = [0] * (self.n) 


    def new_ld(self):
        self.ld = LDEI()
        
    def get_n(self):
        return self.n

    def get_t(self):
        return self.t

    def get_l(self):
        return self.l

    def get_q(self):
        return self.q

    def get_h(self):
        return self.h

    def get_pk(self):
        return self.pk

    def get_P(self):
        return self.P

    def get_alpha(self):
        return self.alpha


    def get_encrypted_fragments(self):
        return self.encrypted_fragments

    def get_revealed_fragments(self):
        return self.revealed_fragments

    def get_ld(self):
        return self.ld

    def get_dl(self):
        return self.dl

 
