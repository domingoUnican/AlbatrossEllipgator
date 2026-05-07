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
        self.albatross._ALBATROSS__crear_matriz_vandermonde.return_value = np.array([[1, 1, 1, 1, 1], [1, 1, 1, 1, 1]])
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

    # =====================================================================
    # TEST 6: LÍMITE EXACTO DE SUPERVIVENCIA (QUÓRUM BFT)
    # =====================================================================
    def test_reconstruction_exact_quorum_survival(self):
        """Verifica el límite matemático para ver su escalabilidad: sobrevivir con exactamente (n - t) nodos"""
        self.albatross.mode = config.CLASSIC_MODE
        self.albatross._ALBATROSS__num_participants = 5
        self.albatross._ALBATROSS__t = 1
        # Límite de supervivencia: r = 5 - 1 = 4. Necesitamos 4 nodos sanos.

        # Simulamos que 1 nodo falla (nos quedan exactamente 4 sanos)
        failed_nodes = [2]
        self.albatross._ALBATROSS__successful_reveal_ids = [0, 1, 3, 4]

        # Configuramos la red
        self.network_mock.EC = False
        self.network_mock.h = 2
        self.network_mock.p = 97

        # Simulamos que la multiplicación matriz devuelve un array de 4x1 (el tamaño exacto del quórum)
        self.albatross._ALBATROSS__multiplicar_matrices.return_value = np.array([[1], [2], [3], [4]])

        try:
            # Si crashea aquí, el cálculo del límite 'r' está mal (o es off-by-one, ej: > en vez de >=)
            self.ejecutar_reconstruccion(failed_nodes)
        except ValueError as e:
            self.fail(
                f"Fallo de límite BFT: El sistema abortó cuando tenía exactamente el quórum necesario. Error: {e}")

    # =====================================================================
    # TEST 7: ALINEACIÓN DE ÍNDICES VANDERMONDE (MATHEMATICAL SLICING)
    # =====================================================================
    def test_reconstruction_vandermonde_index_alignment(self):
        """Asegura que si el Nodo 2 falla, no se utilicen sus datos en Vandermonde garantizando
        la correspondencia entre nodods supervivientes y datos utilizados"""
        self.albatross.mode = config.CLASSIC_MODE

        # Simulamos que el nodo 1 ha fallado
        failed_nodes = [1]
        self.albatross._ALBATROSS__successful_reveal_ids = [0, 2, 3, 4]  # Faltan los datos del 1

        # Simulamos una matriz de Vandermonde completa (5 filas x N columnas)
        matriz_completa = np.array([
            [10, 11, 12, 13, 14],  # El 11 pertenece al nodo 1 que está muerto
            [10, 11, 12, 13, 14]
        ])
        self.albatross._ALBATROSS__crear_matriz_vandermonde.return_value = matriz_completa
        self.albatross._ALBATROSS__multiplicar_matrices.return_value = np.array([[999]])

        self.ejecutar_reconstruccion(failed_nodes)

        # Capturamos la matriz reducida que Albatross intentó enviar a la multiplicación
        args_multiplicacion = self.albatross._ALBATROSS__multiplicar_matrices.call_args[0]
        matriz_vander_filtrada = args_multiplicacion[0]

        # Comprobaciones matemáticas críticas:
        # 1. La fila del nodo caído (11, 11) NO debe estar en la matriz final
        self.assertNotIn(11, matriz_vander_filtrada, "Fallo algorítmico: La matriz usa la fila del nodo muerto.")
        # 2. Las filas de los supervivientes SÍ deben estar
        self.assertIn(10, matriz_vander_filtrada)
        self.assertIn(12, matriz_vander_filtrada)
        self.assertIn(13, matriz_vander_filtrada)
        self.assertIn(14, matriz_vander_filtrada)

    # =====================================================================
    # TEST 8: CORRUPCIÓN DE ENTRADA (NODOS DUPLICADOS)
    # =====================================================================
    def test_reconstruction_duplicate_node_handling(self):
        """Verifica que si la red manda IDs duplicados, el BFT no es engañado,
        evitando ataques de Sybil básicos o problemas de peticiones duplicadas en el servidor HTTP. No
        obstant,e como se usan Set esto no debería ser ningún problema"""
        self.albatross._ALBATROSS__t = 2  # El sistema soporta 2 caídas

        # CAEN 3 NODOS (0, 1 y 2), por lo que el sistema DEBERÍA ABORTAR
        # Pero el sistema de red se vuelve loco y manda una lista repetida engañosa:
        failed_nodes = [0, 0, 1]

        # Realmente solo han revelado los nodos 3 y 4 (que son 2 nodos, insuficientes)
        # Metemos a un tramposo que manda su ID dos veces para simular quórum
        self.albatross._ALBATROSS__successful_reveal_ids = [3, 4, 4, 4]

        with self.assertRaises(ValueError) as context:
            self.ejecutar_reconstruccion(failed_nodes)

        self.assertTrue(
            "Imposible recuperar" in str(context.exception) or "Fallo crítico" in str(context.exception),
            "Fallo de Seguridad: El protocolo fue engañado por un Sybil Attack (Nodos duplicados)"
        )

if __name__ == '__main__':
    unittest.main()