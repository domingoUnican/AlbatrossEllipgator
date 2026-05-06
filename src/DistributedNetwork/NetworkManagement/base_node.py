import requests
import threading

from abc import ABC, abstractmethod

from ..NetworkCommunication.ledger import Ledger
from ALBATROSSProtocol.PPVSSProtocol.PPVSS import PPVSS

class BaseNode(ABC):
    def __init__(self, id, node_type, n):
        self.id = id
        self.node_type = node_type
        self.n = n
        self.neighbors = []
        self.P = []
        self.S = []
        self.dec_frag = []
        self.ledgers = [None] * n

        # Candado global para proteger la memoria compartida en la simulación
        self._SIMULATION_SYNC_LOCK = threading.Lock()

    def set_neighbors(self, neighbors):
        for neighbor in neighbors:
            if neighbor not in self.neighbors:
                self.neighbors.append(neighbor)

    def sync_all_nodes(self):
        """
                Simulación de propagación Gossip P2P en red (Sin HTTP centralizado).
                Usa un Lock para evitar Race Conditions (list index out of range)
                al simular concurrencia masiva en la misma memoria RAM.
                """

        """
        # Version HTTP old
                try:
            response = requests.get("http://localhost:5000/sync_nodes")
            if response.status_code != 200:
                print(f"Error en la sincronización: {response.status_code} - {response.text}")
        except requests.exceptions.RequestException as e:
            print(f"Error en la solicitud de sincronización: {e}")
        """
        with self._SIMULATION_SYNC_LOCK:
            # Algoritmo BFS para que el mensaje de sincronización viaje por toda la red
            visitados = set()
            cola = [self]

            while cola:
                current_node = cola.pop(0)
                if current_node.id not in visitados:
                    visitados.add(current_node.id)
                    current_node.gossip_sync()

                    # Añadimos los vecinos de este nodo a la cola de propagación
                    for neighbor in current_node.neighbors:
                        if neighbor.id not in visitados:
                            cola.append(neighbor)

    def gossip_sync(self):
        for neighbor in self.neighbors:
            self._sync_all_ledgers_with_neighbor(neighbor)

    def commit(self):
        ledger: Ledger = self.ledgers[self.id]
        ledger.new_ld()
        self.P, self.S, self.dec_frag = PPVSS(ledger).distribute()
        ledger.P = self.P
        self.sync_all_nodes()

        # LDEI (HTTP version: old)
        """
        for node_id in range(ledger.n):
            if node_id != self.id: 
                try:
                    response = requests.get(f"http://localhost:5000/node/{node_id}/verify_lde/{self.id}")
                    if not(response.status_code == 200): 
                        print(f"The LDEI verification {self.id} in node {node_id} was incorrect: {response.status_code}")
                except requests.exceptions.RequestException as e:
                    print(f"Error in LDEI verification request at node {node_id}: {e}")
        """

        # LDEI (Gossip/Direct verification)
        for neighbor in self.neighbors:
            try:
                # Llamamos a la función directamente en el objeto del vecino
                if not neighbor.verifie_LDEI(self.id):
                    print(f"The LDEI verification {self.id} in neighbor {neighbor.id} was incorrect.")
            except Exception as e:
                print(f"Error in LDEI verification request at neighbor {neighbor.id}: {e}")

        return "Commit completed"

    def reveal(self):
        ledger: Ledger = self.ledgers[self.id]
        if self.node_type == "MALICIOUS":
            ledger.P = [1]
        else:
            ledger.P = self.P

        self.sync_all_nodes()

        # Verify polynomial (HTTP version, old)
        """
        for node_id in range(ledger.n):
            if node_id != self.id: 
                try:
                    response = requests.get(f"http://localhost:5000/node/{node_id}/verify_polynomial/{self.id}")
                    if not(response.status_code == 200): 
                        print(f"The polynomial verification uploaded by node {self.id} was incorrect: {response.status_code}")
                        return "verify_polynomial operation failed", 400
                except requests.exceptions.RequestException as e:
                    print(f"Error in polynomial verification at node {node_id}: {e}")
        """

        # Verify polynomial (Gossip/Direct verification)
        for neighbor in self.neighbors:
            try:
                if not neighbor.verify_polynomial(self.id):
                    print(
                        f"The polynomial verification uploaded by node {self.id} was incorrect at neighbor {neighbor.id}.")
                    return "verify_polynomial operation failed", 400
            except Exception as e:
                print(f"Error in polynomial verification at neighbor {neighbor.id}: {e}")

        return "Reveal completed"

    def recovery(self, failed_nodes):
        ledger: Ledger = self.ledgers[self.id]

        self._decrypt_fragment(failed_nodes)

        self.sync_all_nodes()

        # Check that the decrypted fragments are correct (HTTP version, old)
        """
        for node_id in range(ledger.n):
            try:
                failed_nodes_str = ','.join(map(str, failed_nodes))
                response = requests.get(f"http://localhost:5000/node/{node_id}/verify_dleq/{self.id}?failed_nodes={failed_nodes_str}")

                if not(response.status_code == 200): 
                    print(f"The DLEQ verification {self.id} at node {node_id} was incorrect: {response.status_code}")
                    return "verify_dleq operation failed", 400

            except requests.exceptions.RequestException as e:
                print(f"Error in DLEQ verification request at node {node_id}: {e}")
        """

        # Check that the decrypted fragments are correct (Gossip/Direct verification)
        for neighbor in self.neighbors:
            try:
                if not neighbor.verifie_DELQ(self.id, failed_nodes):
                    print(f"The DLEQ verification {self.id} at neighbor {neighbor.id} was incorrect.")
                    return "verify_dleq operation failed", 400
            except Exception as e:
                print(f"Error in DLEQ verification request at neighbor {neighbor.id}: {e}")

        return "Decryption correct"

    def _sync_all_ledgers_with_neighbor(self, neighbor: "BaseNode"):
        for i in range(len(self.ledgers)):
            self_ledger = self.ledgers[i]
            neighbor_ledger = neighbor.ledgers[i]

            if neighbor_ledger is None:
                continue

            if self_ledger is None:
                self.ledgers[i] = neighbor_ledger
            else:
                self._sync_single_ledger(self_ledger, neighbor_ledger)

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

    def output(self):
        # Convertimos los shares a strings hexadecimales para la red
        lista_hex = [hex(int(x)) for x in self.S]
        return lista_hex

    def get_id(self):
        return self.id

    def get_neighbors(self) -> list["BaseNode"]:
        return self.neighbors

    @abstractmethod
    def verifie_LDEI(self, ledger_id):
        """Obligado de implementar en el hijo"""
        raise NotImplementedError("El hijo debe implementar LDEI")

    @abstractmethod
    def verifie_DELQ(self, decrypt_id, failed_nodes):
        """Obligado de implementar en el hijo"""
        raise NotImplementedError("El hijo debe implementar DELQ")

    @abstractmethod
    def _decrypt_fragment(self, failed_nodes):
        """Obligado de implementar en el hijo"""
        raise NotImplementedError("El hijo debe desencriptarlos: Clásica inverso del pow, EC usa escaleras")

    @abstractmethod
    def verify_polynomial(self, poly_id):
        """Obligado de implementar en el hijo"""
        raise NotImplementedError("El hijo debe implementar la verificacion del polinomio: Clásica hace pow, EC multiplica puntos")

    @abstractmethod
    def reconstruction(self, failed_node, reco_parties):
        """Obligado de implementar en el hijo"""
        raise NotImplementedError("El hijo debe implementar la reconstrucción: Clásica pide un entero y EC un punto")

    @abstractmethod
    def _sync_single_ledger(self, ledger: Ledger, neighbor_ledger: Ledger):
        """Obligado de implementar en el hijo"""
        raise NotImplementedError("El hijo debe implementar la sincronización del ledger: Clásica busca ceros y EC None")