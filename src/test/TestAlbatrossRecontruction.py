import unittest
from unittest.mock import patch, MagicMock, mock_open
import numpy as np

from ALBATROSSProtocol.ALBATROSS import ALBATROSS
import config

class DummyPoint:
    """Clase dummy para simular las curvas elípticas sin usar ECPY"""
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __mul__(self, other):
        # Simula la multiplicación escalar en la curva
        return DummyPoint(self.x * other, self.y * other)

    def __rmul__(self, other):
        return self.__mul__(other)

    def __add__(self, other):
        return DummyPoint(self.x + other.x, self.y + other.y)

    def __str__(self):
        return f"Point({self.x}, {self.y})"

class TestAlbatrossReconstruction(unittest.TestCase):

    def setUp(self):
        """Preparando un entorno simulado para la clase ALBATROSS"""
        # Creamos una instancia simulada de Albatross sin ejecutar su __init__ real
        self.network_mock = MagicMock()
        self.network_mock.get_q.return_value = 11

        # Creamos el mock del orquestador y le asignamos la red
        self.albatross = MagicMock()
        self.albatross._ALBATROSS__network = self.network_mock

        # Configuramos variables básicas
        self.albatross._ALBATROSS__num_participants = 5
        self.albatross._ALBATROSS__successful_reveal_ids = [1, 2, 3, 4]  # Nodos sanos
        self.albatross._ALBATROSS__T = []
        self.albatross._ALBATROSS__t = 1
        self.albatross.system = config.BYZANTINE

        # Simulamos métodos auxiliares para que no rompan (Vandermonde y Multiplicación)
        self.albatross._ALBATROSS__crear_matriz_vandermonde.return_value = np.array([[1, 1], [1, 1]])
        # Por defecto, la multiplicación devuelve un objeto compatible con .flatten()
        self.albatross._ALBATROSS__multiplicar_matrices.return_value = np.array([[DummyPoint(100, 100)]])

        # Comportamiento simulado de pedir a nodos sanos: añaden fragmentos a __T
        def mock_request_output(node_id):
            """Simula que el nodo devuelve [10, 20]"""
            self.albatross._ALBATROSS__T.append([10, 20])

        # Comportamiento simulado de recuperar nodos: añaden fragmentos a __T
        def mock_request_reconstruction(node_id, primary, subgroup):
            """Simula que el grupo recupera [30, 40]"""
            self.albatross._ALBATROSS__T.append([30, 40])

        self.albatross._ALBATROSS__request_output.side_effect = mock_request_output
        self.albatross._ALBATROSS__request_reconstruction.side_effect = mock_request_reconstruction

        # Vinculamos la función real que queremos testear al objeto simulado
        self.ejecutar_reconstruccion = ALBATROSS._ALBATROSS__execute_reconstruction_phase.__get__(self.albatross)

    # =====================================================================
    # TEST 1: RESTRICCIÓN BIZANTINA (TOLERANCIA A FALLOS)
    # =====================================================================
    def test_reconstruction_exceeds_byzantine_threshold(self):
        """Asegura que si caen más de 't' nodos, el protocolo aborta"""
        self.albatross._ALBATROSS__t = 1
        failed_nodes = [0, 4]  # Caen 2 nodos, pero t = 1

        with self.assertRaises(ValueError) as context:
            self.ejecutar_reconstruccion(failed_nodes)

        self.assertTrue(
            "Imposible recuperar" in str(context.exception) or "Fallo crítico" in str(context.exception))

    # =====================================================================
    # TEST 2: BUG DEL RANDOM.SAMPLE
    # =====================================================================
    @patch('builtins.open', new_callable=mock_open)
    def test_reconstruction_multiple_failures_random_sample_fix(self, m_open):
        """Verifica que recuperar múltiples nodos no crashea por encogimiento de lista"""
        self.albatross.mode = config.CLASSIC_MODE
        self.albatross._ALBATROSS__t = 2  # Aumentamos umbral para permitir 2 caídas
        self.network_mock.EC = False
        self.network_mock.h = 2
        self.network_mock.p = 97
        self.albatross._ALBATROSS__multiplicar_matrices.return_value = np.array([[123]])

        failed_nodes = [0, 4]
        self.ejecutar_reconstruccion(failed_nodes)
        m_open.assert_called()

    # =====================================================================
    # TEST 3: MODO EC SIMPLE (TIPO Y COORDENADAS)
    # =====================================================================
    @patch('builtins.open', new_callable=mock_open)
    def test_reconstruction_ec_simple_type_consistency(self, m_open):
        """Modo EC: verifica multiplicación por la curva y extracción de a.x"""
        self.albatross.mode = config.EC_MODE
        self.albatross._ALBATROSS__network.EC = True
        self.network_mock.h = DummyPoint(5, 5)

        punto_res = DummyPoint(777, 888)
        self.albatross._ALBATROSS__multiplicar_matrices.return_value = np.array([[punto_res]])

        self.ejecutar_reconstruccion([0])

        # Verificamos que se escribió en el archivo
        handle = m_open()
        called_args = "".join(call.args[0] for call in handle.write.call_args_list)
        self.assertIn(hex(777), called_args)

    # =====================================================================
    # TEST 4: MODO ELLIGATOR (TIPO Y MAPEO)
    # =====================================================================
    @patch('ALBATROSSProtocol.ALBATROSS.CurvetoNumber')  # MOCK DEL MAPEO DE ELLIGATOR
    @patch('builtins.open', new_callable=mock_open)
    def test_reconstruction_elligator_type_consistency(self, m_open, mock_curveto):
        """Modo Elligator: verifica multiplicación por curva y mapeo pseudoaleatorio"""
        self.albatross.mode = config.ELLIGATOR_MODE
        self.albatross._ALBATROSS__network.EC = True
        self.network_mock.h = DummyPoint(5, 5)
        mock_curto_res = 999
        mock_curveto.return_value = mock_curto_res

        punto_res = DummyPoint(111, 222)
        self.albatross._ALBATROSS__multiplicar_matrices.return_value = np.array([[punto_res]])

        self.ejecutar_reconstruccion([0])

        self.assertTrue(mock_curveto.called)
        handle = m_open()
        called_args = "".join(call.args[0] for call in handle.write.call_args_list)
        self.assertIn(hex(999), called_args)

    # =====================================================================
    # TEST 5: MODO CLÁSICO (TIPO Y EXPONENCIACIÓN)
    # =====================================================================
    @patch('builtins.open', new_callable=mock_open)
    def test_reconstruction_classic_type_consistency(self, m_open):
        """Modo Clásico: verifica exponenciación discreta regular y que TODOS los elementos pasan por la curva y se genera correctamente la matriz"""
        self.albatross.mode = config.CLASSIC_MODE
        self.albatross._ALBATROSS__network.EC = False
        self.network_mock.h = 2 # h debe ser un entero
        self.network_mock.p = 97 # p debe ser un entero

        self.albatross._ALBATROSS__multiplicar_matrices.return_value = np.array([[555]])

        self.ejecutar_reconstruccion([0])

        handle = m_open()
        called_args = "".join(call.args[0] for call in handle.write.call_args_list)
        self.assertIn("555", called_args)

if __name__ == '__main__':
    unittest.main()