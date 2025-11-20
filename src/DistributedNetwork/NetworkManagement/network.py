import math
import random
import matplotlib.pyplot as plt
import networkx as nx
import sys
from pathlib import Path
sys.path[0] = str(Path(sys.path[0]).parent)
from DistributedNetwork.NetworkManagement.node import Node
from DistributedNetwork.NetworkManagement.node_EC import Node_EC
from ecpy.curves import Curve, Point
from ALBATROSSProtocol.PPVSSProtocol.utils import Utils

class Network:
    def __init__(self, num_nodes, EC=True):
        self.__nodes: list[Node] = []
        self.n = num_nodes
        self.EC = EC
        if EC:
            self.EC = Curve.get_curve('Curve25519') # es de 256
            self.q = self.EC._domain["order"]
            self.h = self.EC._domain["generator"]
        else:           
            k = 128
            size =1024
            self.q, self.p = Utils.findprime(k, size - k)  # Generated q and p
            gen = Utils.generator(self.p)
            self.h = pow(gen, 2, self.p)  # Group generator

    def create_nodes(self, malicious_participants):
        # Initialization data
        count_mal=0
        for i in range(self.n):
            # Type selection
            if i < malicious_participants:
                node_type = "MALICIOUS"
            else:
                node_type = "HONEST"

            if self.EC:
                self.__nodes.append(Node_EC(i, node_type, self.n, self.q, self.h))
            else:
                self.__nodes.append(Node(i, node_type, self.n, self.q, self.p, self.h))
            """
            r = random.random()
            if r < 0.8 or count_mal>self.n//3: #Aquí comprobamos que no se nos descontrolen los maliciosos.
                node_type = "HONEST"
            else:
                node_type = "MALICIOUS"
                count_mal+=1
                print(i,node_type)
            if self.EC:
                self.__nodes.append(Node_EC(i, node_type, self.n, self.q, self.h))
            else:
                self.__nodes.append(Node(i, node_type, self.n, self.q, self.p, self.h))
            """

    def get_q(self):
        return self.q
    

    def get_p(self):
        return self.p


    def get_h(self):
        return self.h


    def pk_to_ledger(self):
        self.sync_nodes()
        for node in self.__nodes:
            node.upload_pk_to_ledger()


    def sync_nodes(self, iterations=50):
        """Performs multiple rounds of synchronization to propagate public keys."""
        for _ in range(iterations):
            for node in self.__nodes:
                node.gossip_sync()


    def assign_neighbors(self):
        # Step 1: Connect the nodes in a linear chain to ensure connectivity
        for i in range(len(self.__nodes) - 1):
            self.__nodes[i].set_neighbors([self.__nodes[i + 1]])
            self.__nodes[i + 1].set_neighbors([self.__nodes[i]])

        # Step 2: Add random additional neighbors
        max_neighbors = int(math.sqrt(len(self.__nodes)))
        for node in self.__nodes:
            additional_neighbors = random.sample(
                [n for n in self.__nodes if n != node and n not in node.get_neighbors()],
                k=min(max_neighbors - len(node.get_neighbors()), len(self.__nodes) - 1)
            )
            node.set_neighbors(node.get_neighbors() + additional_neighbors)


    def get_nodes(self):
        return self.__nodes


    def visualize_network(self):
        G = nx.Graph()

        # Add nodes to the graph
        for node in self.__nodes:
            G.add_node(node.get_id(), label=node.node_type)

        # Add edges (connections between nodes)
        for node in self.__nodes:
            for neighbor in node.get_neighbors():
                G.add_edge(node.get_id(), neighbor.get_id())

        # Draw the network
        pos = nx.spring_layout(G)  # Layout for the graph
        node_labels = nx.get_node_attributes(G, 'label')

        nx.draw(G, pos, with_labels=False, node_size=500, node_color="skyblue", font_size=10, font_color="black")
        nx.draw_networkx_labels(G, pos, labels=node_labels, font_size=8)
        plt.title("Network Visualization")
        plt.show()


if __name__ == '__main__':
    myred = Network(4,EC=True)
    myred.create_nodes()
    myred.assign_neighbors()
    myred.pk_to_ledger()

    minodo =myred.get_nodes()[0]
    print(minodo.node_type)
    print(minodo.ledgers)
    print(minodo.pk)
    minodo.commit()
