import random
import requests

from ..NetworkCommunication.ledger import Ledger
from sympy.polys.galoistools import gf_multi_eval
from sympy.polys.domains import ZZ 
from ALBATROSSProtocol.PPVSSProtocol.PPVSS import PPVSS
from ALBATROSSProtocol.Proofs.DLEQ import DLEQ


class Node: 
    def __init__(self, id, node_type, n, q, p, h):
        self.id = id
        self.node_type = node_type  # Node type: HONEST and MALICIOUS
        self.ledgers: list[Ledger] = [None] * n
        self.ledgers[id] = Ledger(n, q, p, h)
        self.sk = random.randint(0, q - 1)
        self.pk = pow(h, self.sk, p)
        self.neighbors: list[Node] = []   
        self.P = []
        self.S = []
        self.dec_frag = []


    def verifie_LDEI(self, ledger_id):
        ledger: Ledger = self.ledgers[ledger_id]

        if not ledger.ld.verificar(ledger.q, ledger.p, ledger.pk, ledger.alpha, ledger.t + ledger.l, ledger.encrypted_fragments):
            print("The LDEI proof is not correct...")
            return False
        return True
    
    def verifie_DELQ(self, decrypt_id, failed_nodes):
        my_ledger: Ledger = self.ledgers[self.id]
        for node_id in failed_nodes:
            failed_ledger: Ledger = self.ledgers[node_id]
        
            g = [my_ledger.pk[decrypt_id], failed_ledger.encrypted_fragments[decrypt_id]]
            x = [my_ledger.h, failed_ledger.revealed_fragments[decrypt_id]]
            if not failed_ledger.get_dl()[decrypt_id].verificar(my_ledger.q, my_ledger.p, g, x):
                print("The DELQ proof is not correct...")
                return False
            return True

    def verify_polynomial(self, poly_id):
        ledger: Ledger = self.ledgers[poly_id]
        # 2- Each node checks that the polynomial is correct.
        evaluations = [gf_multi_eval(ledger.P, [i % ledger.q], ledger.q, ZZ)[0] for i in range(-ledger.l + 1, ledger.n + 1)]
        encrypted_fragments = [pow(ledger.pk[i], evaluations[i + ledger.l], ledger.p) for i in range(ledger.n)]
        for i in range(ledger.n):
            if not (encrypted_fragments[i] == ledger.encrypted_fragments[i]):
                print("The polynomial published by node {node_id} is not correct.")
                return False
        return True


    def commit(self):
        ledger: Ledger = self.ledgers[self.id]
        ledger.new_ld()
        self.P, self.S, self.dec_frag = PPVSS(ledger).distribute()
        ledger.P = self.P
        self.sync_all_nodes()

        # LDEI
        for node_id in range(ledger.n):
            if node_id != self.id: 
                try:
                    response = requests.get(f"http://localhost:5000/node/{node_id}/verify_lde/{self.id}")
                    if not(response.status_code == 200): 
                        print(f"The LDEI verification {self.id} in node {node_id} was incorrect: {response.status_code}")
                except requests.exceptions.RequestException as e:
                    print(f"Error in LDEI verification request at node {node_id}: {e}")
        
        return "Commit completed."
    
    def reveal(self):
        ledger: Ledger = self.ledgers[self.id]
        if self.node_type == "MALICIOUS":
            ledger.P = [1]
        else:
            ledger.P = self.P
        # Uncomment to make all nodes honest.
        # ledger.P = self.P 

        self.sync_all_nodes()

        # Verify polynomial 
        for node_id in range(ledger.n):
            if node_id != self.id: 
                try:
                    response = requests.get(f"http://localhost:5000/node/{node_id}/verify_polynomial/{self.id}")
                    if not(response.status_code == 200): 
                        print(f"The polynomial verification uploaded by node {self.id} was incorrect: {response.status_code}")
                        return "verify_polynomial operation failed", 400
                except requests.exceptions.RequestException as e:
                    print(f"Error in polynomial verification at node {node_id}: {e}")

        return "Reveal completed."
        
    def recovery(self, failed_nodes):

        ledger: Ledger = self.ledgers[self.id]

        self.__decrypt_fragment(failed_nodes)

        self.sync_all_nodes()

        # Check that the decrypted fragments are correct
        for node_id in range(ledger.n):
            try:
                failed_nodes_str = ','.join(map(str, failed_nodes))
                response = requests.get(f"http://localhost:5000/node/{node_id}/verify_dleq/{self.id}?failed_nodes={failed_nodes_str}")

                if not(response.status_code == 200): 
                    print(f"The DLEQ verification {self.id} at node {node_id} was incorrect: {response.status_code}")
                    return "verify_dleq operation failed", 400

            except requests.exceptions.RequestException as e:
                print(f"Error in DLEQ verification request at node {node_id}: {e}")

        return "Decryption correct"
        
    def reconstruction(self, failed_node, reco_parties):
        
        ledger: Ledger = self.ledgers[failed_node]
        for i, e in enumerate(reco_parties):
            reco_parties[i] = e

        sec = PPVSS(ledger).reconstruct(reco_parties)
        lista_sec = [int(x) for x in sec]
        return lista_sec

    def output(self):
        lista_int = [int(x) for x in self.S]
        return lista_int



    def sync_all_nodes(self):
        try:
            response = requests.get("http://localhost:5000/sync_nodes")
            if response.status_code != 200:
                print(f"Error en la sincronización: {response.status_code} - {response.text}")
        except requests.exceptions.RequestException as e:
            print(f"Error en la solicitud de sincronización: {e}")

    def gossip_sync(self):
        for neighbor in self.neighbors:
            self.__sync_all_ledgers_with_neighbor(neighbor)

    def __sync_all_ledgers_with_neighbor(self, neighbor: "Node"):
        for i in range(len(self.ledgers)):
            self_ledger = self.ledgers[i]
            neighbor_ledger = neighbor.ledgers[i]
            
            if neighbor_ledger is None:
                continue
            
            if self_ledger is None:
                self.ledgers[i] = neighbor_ledger
            else:
                self.__sync_single_ledger(self_ledger, neighbor_ledger)

    def __sync_single_ledger(self, ledger: Ledger, neighbor_ledger: Ledger):
        if ledger.P == [] and neighbor_ledger.P != []:
            ledger.P = neighbor_ledger.P

        if not ledger.alpha and neighbor_ledger.alpha:
            ledger.alpha = neighbor_ledger.alpha

        if ledger.r == 0 and neighbor_ledger.r > 0:
            ledger.r = neighbor_ledger.r

        for i in range(len(ledger.pk)):
            if ledger.pk[i] == 0 and neighbor_ledger.pk[i] != 0:
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



    def __decrypt_fragment(self, failed_nodes):
        my_ledger: Ledger = self.ledgers[self.id]
        invsk = pow(self.sk, -1, my_ledger.q)
        for node_id in failed_nodes:
            other_ledger: Ledger = self.ledgers[node_id]
            encrypted_fragment = other_ledger.encrypted_fragments[self.id]
            decrypted_fragment = pow(encrypted_fragment, invsk, my_ledger.p)
            other_ledger.revealed_fragments[self.id] = decrypted_fragment
            other_ledger.dl[self.id] = DLEQ()
            g = [self.pk, encrypted_fragment]
            x = [my_ledger.h, decrypted_fragment]
            other_ledger.dl[self.id].probar(my_ledger.q, my_ledger.p, g, x, invsk)

    def upload_pk_to_ledger(self):
        for i in range(len(self.ledgers)):
            ledger = self.ledgers[i]
            if ledger is None:
                print(f"Error: Ledger en la posición {i} es None.")
            else:
                if hasattr(ledger, 'pk'):
                    pass
                else:
                    print(f"Error: Ledger en la posición {i} no tiene atributo 'pk'.")
            if ledger is not None and hasattr(ledger, 'pk'):
                ledger.pk[self.id] = self.pk
            else:
                print(f"Error al intentar asignar pk al ledger {i}.")

    def set_neighbors(self, neighbors):
        for neighbor in neighbors:
            if neighbor not in self.neighbors:
                self.neighbors.append(neighbor)

    def get_id(self):
        return self.id

    def get_neighbors(self) -> list["Node"]:
        return self.neighbors
