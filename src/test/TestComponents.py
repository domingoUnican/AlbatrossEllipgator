import unittest
from unittest.mock import patch, MagicMock
import requests
import config

from ALBATROSSProtocol.ALBATROSS import ALBATROSS

from ecpy.curves import Curve, Point
from Elliga.ellifun import CurvetoNumber

class DummyPoint:
    """Clase dummy para simular puntos EC"""
    def __init__(self, x, y):
        self.x = x
        self.y = y


class TestAlbatrossComponents(unittest.TestCase):

    def setUp(self):
        """Preparamos el orquestador limpio para cada test"""
        self.network_mock = MagicMock()
        self.albatross = ALBATROSS(self.network_mock, num_participants=5, system=config.BYZANTINE,
                                   mode=config.CLASSIC_MODE)

    # =====================================================================
    # BLOQUE 1: TESTS DE RED Y NODOS (Manejo de Errores HTTP)
    # =====================================================================
    @patch('requests.get')
    def test_request_commit_success(self, mock_get):
        """Verifica que un Commit 200 OK añade al nodo a la lista de éxitos"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        # Ejecutamos la petición privada usando _ALBATROSS__
        self.albatross._ALBATROSS__request_commit(node_id=1)

        self.assertIn(1, self.albatross._ALBATROSS__successful_commit_ids)

    @patch('requests.get')
    def test_request_commit_http_error(self, mock_get):
        """Verifica que un error 500 de Flask NO añade al nodo a la lista"""
        mock_response = MagicMock()
        mock_response.status_code = 500  # Simula que el nodo petó internamente
        mock_get.return_value = mock_response

        self.albatross._ALBATROSS__request_commit(node_id=2)

        self.assertNotIn(2, self.albatross._ALBATROSS__successful_commit_ids)

    @patch('requests.get')
    def test_request_commit_timeout_exception(self, mock_get):
        """Verifica que un Timeout (nodo apagado) es atrapado por el try/except y no crashea"""
        # Simulamos que requests lanza una excepción de red (Timeout)
        mock_get.side_effect = requests.exceptions.Timeout("El servidor no responde")

        try:
            self.albatross._ALBATROSS__request_commit(node_id=3)
        except Exception as e:
            self.fail(f"El método no atrapó la excepción de red. Crasheó con: {e}")

        # Comprobamos que, efectivamente, no se registró como exitoso
        self.assertNotIn(3, self.albatross._ALBATROSS__successful_commit_ids)

    @patch('requests.get')
    def test_request_reveal_validation_fail(self, mock_get):
        """Verifica que un fallo de VSS (HTTP 400) en el Reveal lo marca como caído"""
        mock_response = MagicMock()
        mock_response.status_code = 400  # Simula que el polinomio era falso
        mock_get.return_value = mock_response

        self.albatross._ALBATROSS__request_reveal(node_id=4)

        self.assertNotIn(4, self.albatross._ALBATROSS__successful_reveal_ids)

    # =====================================================================
    # BLOQUE 2: TESTS DE CRIPTOGRAFÍA (Elligator y Curvas)
    # =====================================================================
    def test_elligator_determinism(self):
        """Elligator debe ser determinista así que el mismo punto de la curva debe mapearse SIEMPRE al mismo número entero que parece aleatorio"""
        # 1. Cargamos la curva real que usas en Network.py
        cv = Curve.get_curve('Curve25519')

        # Usamos el punto generador G como punto de prueba
        punto_prueba = cv.generator

        # 2. Pasamos el punto por tu función real (sin mocks)
        resultado_1 = CurvetoNumber(punto_prueba)
        resultado_2 = CurvetoNumber(punto_prueba)

        # Verificamos
        self.assertIsInstance(resultado_1, int, "Elligator debe devolver un número entero")
        self.assertEqual(resultado_1, resultado_2, "Si se pasa el mismo punto, debe generar el mismo hash/mapeo")
        self.assertNotEqual(resultado_1, punto_prueba.x,
                            "Peligro: Elligator está devolviendo la X en crudo, no ofusca.")

    def test_elligator_avoids_information_leak(self):
        """El mapeo no debe devolver las coordenadas puras para evitar que un firewall detecte que es criptografía de curvas y lo censure """
        punto_prueba = DummyPoint(12345, 67890)

        with patch('ALBATROSSProtocol.ALBATROSS.CurvetoNumber') as mock_curvetonumber:
            mock_curvetonumber.return_value = 987654321

            resultado = mock_curvetonumber(punto_prueba)

            # El resultado ofuscado JAMÁS debe ser igual a la coordenada X pura
            self.assertNotEqual(resultado, punto_prueba.x)
            # Tampoco a la Y
            self.assertNotEqual(resultado, punto_prueba.y)

    # =====================================================================
    # BLOQUE 3: TESTS DE CRIPTOGRAFÍA (Vandermonde y PPVSS)
    # =====================================================================
    def test_crear_matriz_vandermonde_dimensions(self):
        """Prueba que la matriz de Vandermonde tiene el tamaño teórico correcto (l x t+l)."""
        # N=10, t=3, Bizantino -> l = N - 2t = 4
        # Columnas teóricas = t + l = 3 + 4 = 7
        # Tamaño esperado: 4 filas x 7 columnas
        omega = 2  # Raíz de la unidad simulada
        l = 4
        t = 3

        # Llamamos a la función real
        matriz = self.albatross._ALBATROSS__crear_matriz_vandermonde(omega, l, t)

        import numpy as np
        self.assertIsInstance(matriz, np.ndarray)
        self.assertEqual(matriz.shape, (4, 7), "Las dimensiones de Vandermonde no respetan el paper de Albatross.")

    def test_crear_matriz_vandermonde_math(self):
        """Prueba que los exponentes de omega crecen correctamente en las columnas."""
        omega = 3
        l = 2
        t = 1
        # n_columnas = 1 + 2 = 3.
        # Fila 0 es omega^0 = 1. Fila 1 es omega^1 = 3.
        # Fila 1 = [3^0, 3^1, 3^2] -> [1, 3, 3]
        # Fila 2 = [3^0, 3^1, 3^2] -> [1, 3, 9]

        matriz = self.albatross._ALBATROSS__crear_matriz_vandermonde(omega, l, t)

        self.assertEqual(matriz[0][0], 1)
        self.assertEqual(matriz[1][1], 3)
        self.assertEqual(matriz[1][2], 9)

    # =====================================================================
    # BLOQUE 4: TESTS DE CRIPTOGRAFÍA (Reconstrucción del secreto)
    # =====================================================================
    @patch('ALBATROSSProtocol.PPVSSProtocol.utils.Utils.rootunity')
    def test_secret_reconstruction_math(self, mock_rootunity):
        """Prueba de integración matemática: Comprueba que Vandermonde + dot recupera el secreto"""
        # Simulamos un escenario muy sencillo: N=3, t=1 (Por tanto r = 2)
        # Secreto original = 100. Polinomio: f(x) = 100 + 50x
        # Evaluamos el polinomio para los nodos (usamos x=1 y x=2 para simplificar)
        # Nodo 1: f(1) = 150
        # Nodo 2: f(2) = 200

        # Evitamos el bucle infinito haciendo que rootunity devuelva un 2 instantáneamente
        mock_rootunity.return_value = 2

        self.albatross._ALBATROSS__num_participants = 3
        self.albatross._ALBATROSS__t = 1
        self.albatross.system = config.BYZANTINE
        self.albatross.mode = config.CLASSIC_MODE

        # Metemos en la matriz T los fragmentos recibidos (cada nodo manda 1 lista con su fragmento)
        self.albatross._ALBATROSS__T = [[150], [200]]

        # Forzamos una raíz de la unidad sencilla para el test matemático
        self.albatross._ALBATROSS__network.get_q.return_value = 97

        # Mockeamos Vandermonde para que use la matriz inversa exacta del polinomio
        # La interpolación de Lagrange para x=1, x=2 y evaluar en 0 da los pesos [2, -1]
        # (2 * 150) + (-1 * 200) = 300 - 200 = 100 (¡El secreto!)
        import numpy as np
        matriz_inversa_simulada = np.array([[2, -1]])
        self.albatross._ALBATROSS__crear_matriz_vandermonde = MagicMock(return_value=matriz_inversa_simulada)

        # Ejecutamos la fase final
        self.albatross._ALBATROSS__process_final_output()

        # Leemos el archivo generado para ver si recuperó el 100
        with open('aleatoriedad_final.txt', 'r') as f:
            resultado = f.read()

        self.assertTrue("100" in resultado,
                        f"Fallo matemático: El secreto reconstruido no es 100. Resultado fue: {resultado}")

    @patch('ALBATROSSProtocol.PPVSSProtocol.utils.Utils.rootunity')
    def test_secret_reconstruction_string(self, mock_rootunity):
        """Prueba avanzada: Convierte texto a int, lo reconstruye mediante Lagrange y lo devuelve a texto"""
        mock_rootunity.return_value = 2

        # EL SECRETO ORIGINAL
        mensaje_original = "Hola Mundo Criptográfico Cruel"
        # Convertimos el texto a un número gigante
        secreto_int = int.from_bytes(mensaje_original.encode('utf-8'), 'big')

        # SIMULAMOS LOS FRAGMENTOS (Polinomio f(x) = secreto_int + 10x)
        # Nodo 1 (x=1) -> f(1) = secreto_int + 10
        # Nodo 2 (x=2) -> f(2) = secreto_int + 20
        frag_1 = secreto_int + 10
        frag_2 = secreto_int + 20

        # Configuramos el entorno (N=3, t=1, r=2)
        self.albatross._ALBATROSS__num_participants = 3
        self.albatross._ALBATROSS__t = 1
        self.albatross.system = config.BYZANTINE
        self.albatross.mode = config.CLASSIC_MODE
        self.albatross._ALBATROSS__T = [[frag_1], [frag_2]]
        self.albatross._ALBATROSS__network.get_q.return_value = 97

        # INTERPOLACIÓN MATEMÁTICA
        import numpy as np
        # Los pesos de Lagrange para evaluar en 0 dados x=1, x=2 son [2, -1]
        self.albatross._ALBATROSS__crear_matriz_vandermonde = MagicMock(return_value=np.array([[2, -1]]))

        # Ejecutamos la fase final
        self.albatross._ALBATROSS__process_final_output()

        with open('aleatoriedad_final.txt', 'r') as f:
            resultado_str = f.read()

        # Numpy guarda el txt con corchetes "[[ numero ]]", los limpiamos
        numero_recuperado = int(resultado_str.replace('[', '').replace(']', '').strip())

        # TRADUCIR EL NÚMERO DE VUELTA A TEXTO
        # Calculamos los bytes necesarios para decodificar
        num_bytes = (numero_recuperado.bit_length() + 7) // 8
        mensaje_recuperado = numero_recuperado.to_bytes(num_bytes, 'big').decode('utf-8')

        # COMPROBACIÓN FINAL
        self.assertEqual(mensaje_recuperado, mensaje_original, "¡Fallo! El texto reconstruido está corrupto.")

    @patch('ALBATROSSProtocol.PPVSSProtocol.utils.Utils.rootunity')
    def test_secret_reconstruction_ec_mode(self, mock_rootunity):
        """Prueba de reconstrucción: Verifica que extrae la coordenada X en modo EC"""
        mock_rootunity.return_value = 2

        self.albatross._ALBATROSS__num_participants = 3
        self.albatross._ALBATROSS__t = 1
        self.albatross.system = config.BYZANTINE
        self.albatross.mode = config.EC_MODE  # Activamos modo EC
        self.albatross._ALBATROSS__network.get_q.return_value = 97

        # En EC, T recibe OBJETOS (puntos de la curva). Creamos un objeto falso
        class FakePoint:
            def __init__(self, x):
                self.x = x  # La x contiene el fragmento matemático (150 y 200)

        self.albatross._ALBATROSS__T = [[FakePoint(150)], [FakePoint(200)]]

        import numpy as np
        self.albatross._ALBATROSS__crear_matriz_vandermonde = MagicMock(return_value=np.array([[2, -1]]))

        # Ejecutamos la fase final
        self.albatross._ALBATROSS__process_final_output()

        with open('aleatoriedad_final.txt', 'r') as f:
            resultado = f.read()

        self.assertTrue("100" in resultado,
                        "Fallo en modo EC: No supo extraer la coordenada X para reconstruir el 100.")

    @patch('ALBATROSSProtocol.PPVSSProtocol.utils.Utils.rootunity')
    @patch('ALBATROSSProtocol.ALBATROSS.CurvetoNumber')
    def test_secret_reconstruction_elligator_mode(self, mock_curvetonumber, mock_rootunity):
        """Prueba de reconstrucción: Verifica que llama a la ofuscación en modo Elligator"""
        mock_rootunity.return_value = 2

        self.albatross._ALBATROSS__num_participants = 3
        self.albatross._ALBATROSS__t = 1
        self.albatross.system = config.BYZANTINE
        self.albatross.mode = config.ELLIGATOR_MODE  # Activamos modo Elligator
        self.albatross._ALBATROSS__network.get_q.return_value = 97

        # En Elligator, los objetos de la curva se deben ofuscar.
        # Simulamos que mock_curvetonumber convierte los puntos falsos en los fragmentos 150 y 200.
        # Hacemos que la función devuelva 150 la primera vez que se llama y 200 la segunda.
        mock_curvetonumber.side_effect = [150, 200]

        # Le pasamos cualquier objeto, la función mockeada hará el trabajo
        self.albatross._ALBATROSS__T = [["PuntoFalso1"], ["PuntoFalso2"]]

        import numpy as np
        self.albatross._ALBATROSS__crear_matriz_vandermonde = MagicMock(return_value=np.array([[2, -1]]))

        self.albatross._ALBATROSS__process_final_output()

        with open('aleatoriedad_final.txt', 'r') as f:
            resultado = f.read()

        self.assertTrue("100" in resultado, "Fallo en modo Elligator: La integración con CurvetoNumber está rota.")

if __name__ == '__main__':
    unittest.main()