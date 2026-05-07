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
        self.albatross._ALBATROSS__T = {}
        self.albatross._ALBATROSS__t = 1
        self.albatross.system = config.BYZANTINE

        # Simulamos métodos auxiliares para que no rompan (Vandermonde y Multiplicación)
        self.albatross._ALBATROSS__crear_matriz_vandermonde.return_value = np.array([[1, 1, 1, 1, 1], [1, 1, 1, 1, 1]])
        # Por defecto, la multiplicación devuelve un objeto compatible con .flatten()
        self.albatross._ALBATROSS__multiplicar_matrices.return_value = np.array([[DummyPoint(100, 100)]])

        # Comportamiento simulado de pedir a nodos sanos: añaden fragmentos a __T
        def mock_request_output(node_id):
            """Simula que el nodo devuelve [10, 20]"""
            self.albatross._ALBATROSS__T[node_id] = [10, 20]

        # Comportamiento simulado de recuperar nodos: añaden fragmentos a __T
        def mock_request_reconstruction(node_id, primary, subgroup):
            """Simula que el grupo recupera [30, 40]"""
            self.albatross._ALBATROSS__T[node_id] = [30, 40]

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
    # TEST 6: LÍMITE EXACTO DE SUPERVIVENCIA (QUORUM BFT)
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
    @patch('ALBATROSSProtocol.PPVSSProtocol.utils.Utils.rootunity')
    def test_reconstruction_vandermonde_index_alignment(self, mock_rootunity):
        """Asegura que si el Nodo 2 falla, no se utilicen sus datos en Vandermonde garantizando
        la correspondencia entre nodods supervivientes y datos utilizados"""
        mock_rootunity.return_value = 2  # Evitamos bucles infinitos

        self.albatross.mode = config.CLASSIC_MODE
        self.albatross._ALBATROSS__num_participants = 5
        self.albatross._ALBATROSS__t = 1
        self.albatross.system = config.BYZANTINE

        # Simulamos que el nodo 1 ha fallado, solo sobreviven 0, 2, 3 y 4
        self.albatross._ALBATROSS__successful_reveal_ids = {0, 2, 3, 4}

        # Simulamos una matriz de Vandermonde completa (2 filas x 5 columnas)
        # El 11 y 21 pertenecen al nodo 1 que está muerto
        matriz_completa = np.array([
            [10, 11, 12, 13, 14],
            [20, 21, 22, 23, 24]
        ])
        self.albatross._ALBATROSS__crear_matriz_vandermonde.return_value = matriz_completa
        self.albatross._ALBATROSS__T = {0: [99], 2: [99], 3: [99], 4: [99]}

        # Interceptamos el méto-do real
        self.albatross._ALBATROSS__multiplicar_matrices = MagicMock(return_value=np.array([[999]]))

        # To-do va bien: se recorta la matriz descartando muertos
        ALBATROSS._ALBATROSS__process_final_output(self.albatross)

        # Capturamos la matriz reducida que Albatross intentó enviar a la multiplicación
        matriz_vander_filtrada = self.albatross._ALBATROSS__multiplicar_matrices.call_args[0][0]

        # Comprobación de seguridad: la columna del Nodo 1 (los valores 11 y 21) deben haber sido eliminados
        self.assertNotIn(11, matriz_vander_filtrada, "La matriz usa la fila del nodo muerto.")
        self.assertNotIn(21, matriz_vander_filtrada)

        # Las columnas sanas sí están
        self.assertIn(10, matriz_vander_filtrada)
        self.assertIn(12, matriz_vander_filtrada)

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

    # =====================================================================
    # TEST 9: E2E MATEMÁTICO (RECUPERACIÓN EXACTA DE UN STRING)
    # =====================================================================
    @patch('ALBATROSSProtocol.PPVSSProtocol.utils.Utils.rootunity')
    @patch('builtins.open', new_callable=mock_open)
    def test_reconstruction_e2e_string_recovery(self, m_open, mock_rootunity):
        """Prueba que la reconstruccion recupera la cadena de texto exacta con álgebra de Numpy"""
        mock_rootunity.return_value = 2

        self.albatross.mode = config.CLASSIC_MODE
        self.albatross._ALBATROSS__num_participants = 3
        self.albatross._ALBATROSS__t = 1

        # Configuramos la red (h=1 para que la exponenciación h^s no altere el secreto original)
        self.network_mock.EC = True
        self.network_mock.h = 1
        self.network_mock.p = 9999999999999999999999999999999 # Primo gigante

        # 1. Secretomoriginal
        mensaje_original = "HOLA MUNDO CRUEL"
        secreto_int = int.from_bytes(mensaje_original.encode('utf-8'), 'big')

        # 2. Simulación de fragmentos con interpolación simple
        # Añadimos un 0 en el medio. Columna 0 = 2, Columna 1 = 0, Columna 2 = -1
        self.albatross._ALBATROSS__crear_matriz_vandermonde.return_value = np.array([[2, 0, -1]])

        # El Nodo 0 y el Nodo 2 responden con fragmentos. El Nodo 1 está muerto.
        frag_0 = secreto_int + 10
        frag_2 = secreto_int + 20
        failed_nodes = [1]
        self.albatross._ALBATROSS__successful_reveal_ids = [0, 2]

        # Configuramos multiplicar_matrices para que haga el np.dot REAL
        def dot_real(vander, matriz_t):
            return np.dot(vander, matriz_t)

        self.albatross._ALBATROSS__multiplicar_matrices.side_effect = dot_real

        # Los fragmentos recibidos en T
        self.albatross._ALBATROSS__T = {0: [frag_0], 2: [frag_2]}

        # Desactivamos los Mocks del setUp para que no añadan basura de [10, 20] a nuestro secreto
        self.albatross._ALBATROSS__request_output.side_effect = lambda x: None
        # Habilitamos la recuperación para que salve al Nodo 1
        # Simulamos que la red recupera un fragmento '0' para el Nodo 1 (porque 2*frag_0 + 0*frag_1 - 1*frag_2 nos dará el string perfecto)
        def mock_recuperacion(node_id, p, s):
            self.albatross._ALBATROSS__T[node_id] = [0]

        self.albatross._ALBATROSS__request_reconstruction.side_effect = mock_recuperacion

        # 3. Ejecuamos la reconstruccion
        self.ejecutar_reconstruccion(failed_nodes)

        # 4. Comprobacion
        handle = m_open()
        called_args = "".join(call.args[0] for call in handle.write.call_args_list)

        # Limpiamos el formato (quitar corchetes, comillas simples y leer hex)
        str_limpio = called_args.replace('[', '').replace(']', '').replace("'", "").strip()
        numero_recuperado = int(str_limpio, 16)

        # Traducir de vuelta a texto
        num_bytes = (numero_recuperado.bit_length() + 7) // 8
        mensaje_recuperado = numero_recuperado.to_bytes(num_bytes, 'big').decode('utf-8')

        self.assertEqual(mensaje_recuperado, mensaje_original, "¡Fallo E2E! El string reconstruido está corrupto.")

if __name__ == '__main__':
    unittest.main()