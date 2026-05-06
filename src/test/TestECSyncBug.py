import unittest

from ecpy.curves import Curve
from DistributedNetwork.NetworkManagement.node_EC import Node_EC
from DistributedNetwork.NetworkCommunication.ledger_EC import Ledger_EC as Ledger

class TestECSyncBug(unittest.TestCase):
    def setUp(self):
        # Esta función se ejecuta antes de cada test para prepararlos
        cv = Curve.get_curve('Curve25519')
        self.G = cv._domain["generator"]
        self.q = cv.order

    def test_1_gossip_sync_none_to_point(self):
        """Prueba que un nodo vacío copie la clave pública de su vecino."""
        t_test = 0
        node_A = Node_EC(id=0, node_type="HONEST", t=t_test, n=2, q=self.q, h=self.G)
        node_B = Node_EC(id=1, node_type="HONEST", t=t_test, n=2, q=self.q, h=self.G)

        # Creamos el Ledger 0 al Nodo B para que puedan comunicarse entre ellos
        node_B.ledgers[0] = Ledger(n=2, q=self.q, t=t_test, h=self.G)

        # El Nodo B guarda su clave
        node_B.ledgers[0].pk[1] = node_B.pk

        # Sincronizamos
        node_A.set_neighbors([node_B])
        node_A.gossip_sync()

        # Prueba 1: comprobamos que no sea None para que ecpy devuelva una excepción
        self.assertIsNotNone(
            node_A.ledgers[0].pk[1],
            "BUG DETECTADO: el Nodo A no ha sincronizado la clave (sigue siendo None)."
        )

        # Prueba 2: comparamos los Puntos
        self.assertEqual(
            node_A.ledgers[0].pk[1],
            node_B.pk,
            "La clave sincronizada no coincide con la original"
        )

    def test_2_no_overwrite_existing_keys(self):
        """Prueba que un nodo no borre una clave que ya tenía guardada"""
        t_test = 0
        node_A = Node_EC(id=0, node_type="HONEST", t=t_test, n=2, q=self.q, h=self.G)
        node_B = Node_EC(id=1, node_type="HONEST", t=t_test, n=2, q=self.q, h=self.G)

        node_B.ledgers[0] = Ledger(n=2, t=t_test, q=self.q, h=self.G)

        # El Nodo A ya tiene una clave guardada (inventada)
        clave_inventada = self.G * 999
        node_A.ledgers[0].pk[1] = clave_inventada

        # El Nodo B tiene su clave suya (real)
        node_B.ledgers[0].pk[1] = node_B.pk

        # Sincronizan
        node_A.set_neighbors([node_B])
        node_A.gossip_sync()

        # El Nodo A debería conservar su clave antigua, NO la de B
        self.assertEqual(
            node_A.ledgers[0].pk[1],
            clave_inventada,
            "BUG LÓGICO: el nodo ha sobreescrito una clave que ya tenía validada"
        )

if __name__ == '__main__':
    unittest.main()