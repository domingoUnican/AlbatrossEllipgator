import random

from ..NetworkCommunication.ledger_EC import Ledger_EC as Ledger, Ledger_EC
from sympy.polys.galoistools import gf_multi_eval
from sympy.polys.domains import ZZ 
from ALBATROSSProtocol.PPVSSProtocol.PPVSS import PPVSS
from ALBATROSSProtocol.Proofs.DLEQ import DLEQ

from .base_node import BaseNode

class Node_EC(BaseNode):
    def __init__(self, id, node_type, n, t, q ,h): #h es ahora el punto aG
        super().__init__(id, node_type, n)

        # Variables exclusivas de criptografía de curvas elípticas
        self.q = q
        self.h = h

        # Inicialización del Ledger para criptografía EC (None en las claves)
        self.ledgers[id] = Ledger_EC(n, t, q, h)
        self.sk = random.randint(0, q - 1)
        self.pk = self.sk * h  # Multiplicación escalar


    def verifie_LDEI(self, ledger_id):
        """Sobreescribiendo el de base_node"""
        ledger: Ledger = self.ledgers[ledger_id]

        if not ledger.ld.verificar_EC(ledger.q, ledger.pk, ledger.alpha, ledger.t + ledger.l, ledger.encrypted_fragments):
            print("The LDEI proof is not correct...")
            return False
        return True
    
    def verifie_DELQ(self, decrypt_id, failed_nodes):
        """Sobreescribiendo el de base_node"""
        my_ledger: Ledger = self.ledgers[self.id]
        for node_id in failed_nodes:
            failed_ledger: Ledger = self.ledgers[node_id]
        
            g = [my_ledger.pk[decrypt_id], failed_ledger.encrypted_fragments[decrypt_id]]
            x = [my_ledger.h, failed_ledger.revealed_fragments[decrypt_id]]
            if not failed_ledger.get_dl()[decrypt_id].verificar_EC(my_ledger.q, g, x):
                print("The DELQ proof is not correct...")
                return False
            return True

    def verify_polynomial(self, poly_id):
        ledger: Ledger = self.ledgers[poly_id]
        # 2- Each node checks that the polynomial is correct.
        evaluations = [gf_multi_eval(ledger.P, [i % ledger.q], ledger.q, ZZ)[0] for i in range(-ledger.l + 1, ledger.n + 1)]
        encrypted_fragments = [evaluations[i + ledger.l]*ledger.pk[i] for i in range(ledger.n)]
        for i in range(ledger.n):
            if not (encrypted_fragments[i] == ledger.encrypted_fragments[i]):
                print("The polynomial published by node {node_id} is not correct.")
                return False
        return True
        
    def reconstruction(self, failed_node, reco_parties):
        
        ledger: Ledger = self.ledgers[failed_node]
        for i, e in enumerate(reco_parties):
            reco_parties[i] = e

        sec = PPVSS(ledger).reconstruct(reco_parties,True)
        # Convertimos los enteros a cadenas hexadecimales (O(N))
        lista_sec_hex = [hex(int(x.x)) for x in sec]
        return lista_sec_hex

    def _sync_single_ledger(self, ledger: Ledger, neighbor_ledger: Ledger):
        if ledger.P == [] and neighbor_ledger.P != []:
            ledger.P = neighbor_ledger.P

        if not ledger.alpha and neighbor_ledger.alpha:
            ledger.alpha = neighbor_ledger.alpha

        if ledger.r == 0 and neighbor_ledger.r > 0:
            ledger.r = neighbor_ledger.r

        for i in range(len(ledger.pk)):
            if ledger.pk[i] is None and neighbor_ledger.pk[i] is not None:
                ledger.pk[i] = neighbor_ledger.pk[i]

        if not ledger.encrypted_fragments and neighbor_ledger.encrypted_fragments:
            ledger.encrypted_fragments = neighbor_ledger.encrypted_fragments

        for i in range(len(ledger.revealed_fragments)):
            if ledger.revealed_fragments[i] == 0 and neighbor_ledger.revealed_fragments[i] != 0:
                ledger.revealed_fragments[i] = neighbor_ledger.revealed_fragments[i]

        if ledger.ld is None and neighbor_ledger.ld is not None:
            ledger.ld = neighbor_ledger.ld

        for i in range(len(ledger.dl)):
            if ledger.dl[i] == 0 and neighbor_ledger.dl[i] != 0:
                ledger.dl[i] = neighbor_ledger.dl[i]

    def _decrypt_fragment(self, failed_nodes):
        my_ledger: Ledger = self.ledgers[self.id]
        invsk = pow(self.sk, -1, my_ledger.q)
        for node_id in failed_nodes:
            other_ledger: Ledger = self.ledgers[node_id]
            encrypted_fragment = other_ledger.encrypted_fragments[self.id]
            decrypted_fragment=invsk*encrypted_fragment
            other_ledger.revealed_fragments[self.id] = decrypted_fragment
            other_ledger.dl[self.id] = DLEQ()
            g = [self.pk, encrypted_fragment]
            x = [my_ledger.h, decrypted_fragment]
            other_ledger.dl[self.id].probar_EC(my_ledger.q, g, x, invsk)
