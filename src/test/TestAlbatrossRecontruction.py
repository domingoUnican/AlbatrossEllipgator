import unittest
from unittest.mock import patch, MagicMock
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

class TestAlbatrossReconstruction(unittest.TestCase):

    def setUp(self):
        """Preparando un entorno simulado para la clase ALBATROSS"""
        # Creamos una instancia simulada de Albatross sin ejecutar su __init__ real
        self.albatross = MagicMock()

        # Configuramos variables básicas
        self.albatross._ALBATROSS__num_participants = 5
        self.albatross._ALBATROSS__successful_reveal_ids = [1, 2, 3, 4]  # Nodos sanos
        self.albatross._ALBATROSS__T = []
        self.albatross._ALBATROSS__t = 1
        self.albatross.system = config.BYZANTINE

        # Simulamos una red EC
        self.albatross._ALBATROSS__network = MagicMock()
        self.albatross._ALBATROSS__network.EC = True
        self.albatross._ALBATROSS__network.h = DummyPoint(5, 5)  # Punto Generador H
        self.albatross._ALBATROSS__network.p = 97
        self.albatross._ALBATROSS__network.get_q.return_value = 11

        # Simulamos métodos auxiliares para que no rompan (Vandermonde y Multiplicación)
        self.albatross._ALBATROSS__crear_matriz_vandermonde.return_value = np.array([[1, 1], [1, 1]])
        self.albatross._ALBATROSS__multiplicar_matrices.return_value = "SECRETO_RECONSTRUIDO"

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
    @patch('builtins.open', new_callable=MagicMock)
    def test_reconstruction_multiple_failures_random_sample_fix(self, mock_open):
        """Verifica que recuperar múltiples nodos no crashea por encogimiento de lista"""
        self.albatross.mode = config.CLASSIC_MODE
        self.albatross._ALBATROSS__t = 2  # Aumentamos umbral para permitir 2 caídas
        failed_nodes = [0, 4]

        try:
            self.ejecutar_reconstruccion(failed_nodes)
        except ValueError as e:
            if "Sample larger than population" in str(e):
                self.fail("Regresó el bug de random.sample: la lista de participantes no se resetea")
            else:
                raise e  # Si es otro error, que lo lance

    # =====================================================================
    # TEST 3: MODO EC SIMPLE (TIPO Y COORDENADAS)
    # =====================================================================
    @patch('numpy.array')
    @patch('builtins.open', new_callable=MagicMock)
    def test_reconstruction_ec_simple_type_consistency(self, mock_open, mock_np_array):
        """Modo EC: verifica multiplicación por la curva y extracción de a.x"""
        self.albatross.mode = config.EC_MODE
        self.albatross._ALBATROSS__network.EC = True
        failed_nodes = [0]

        self.ejecutar_reconstruccion(failed_nodes)

        # Verificamos que np.array fue llamado con una matriz Tprima válida
        self.assertTrue(mock_np_array.called)
        args, _ = mock_np_array.call_args
        t_prima = args[0]

        # En EC Simple, como multiplicamos [10, 20] por DummyPoint(5,5), el resultado son puntos. Tprima debió extraer la 'x' (10*5 = 50).
        for fila in t_prima:
            for elemento in fila:
                self.assertIsInstance(elemento, int)
                self.assertEqual(elemento % 50, 0)  # Matemáticas dummy: 10*5 o 30*5

    # =====================================================================
    # TEST 4: MODO ELLIGATOR (TIPO Y MAPEO)
    # =====================================================================
    @patch('ALBATROSSProtocol.ALBATROSS.CurvetoNumber')  # MOCK DEL MAPEO DE ELLIGATOR
    @patch('numpy.array')
    @patch('builtins.open', new_callable=MagicMock)
    def test_reconstruction_elligator_type_consistency(self, mock_open, mock_np_array, mock_curvetonumber):
        """Modo Elligator: verifica multiplicación por curva y mapeo pseudoaleatorio"""
        self.albatross.mode = config.ELLIGATOR_MODE
        self.albatross._ALBATROSS__network.EC = True
        mock_curvetonumber.return_value = 999  # Simulamos que Elligator retorna siempre 999
        failed_nodes = [0]

        self.ejecutar_reconstruccion(failed_nodes)

        # Elligator debió haber sido llamado para cada punto en la matriz __T
        self.assertTrue(mock_curvetonumber.called)

        args, _ = mock_np_array.call_args
        t_prima = args[0]
        for fila in t_prima:
            for elemento in fila:
                self.assertEqual(elemento, 999, "Los elementos no pasaron por CurvetoNumber")

    # =====================================================================
    # TEST 5: MODO CLÁSICO (TIPO Y EXPONENCIACIÓN)
    # =====================================================================
    @patch('numpy.array')
    @patch('builtins.open', new_callable=MagicMock)
    def test_reconstruction_classic_type_consistency(self, mock_open, mock_np_array):
        """Modo Clásico: verifica exponenciación discreta regular y que TODOS los elementos pasan por la curva y se genera correctamente la matriz"""
        self.albatross.mode = config.CLASSIC_MODE
        self.albatross._ALBATROSS__network.EC = False
        self.albatross._ALBATROSS__network.h = 2
        self.albatross._ALBATROSS__network.p = 97
        failed_nodes = [0]

        self.ejecutar_reconstruccion(failed_nodes)

        args, _ = mock_np_array.call_args
        t_prima = args[0]

        # En Clásico: (2^10 mod 97) = 54.
        # Verificamos que no quedan rastros del "10" original.
        for fila in t_prima:
            for elemento in fila:
                self.assertNotEqual(elemento, 10, "Matriz Frankenstein en Clásico")
                self.assertNotEqual(elemento, 30, "Matriz Frankenstein en Clásico")

if __name__ == '__main__':
    unittest.main()