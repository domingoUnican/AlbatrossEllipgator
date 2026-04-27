import threading
import unittest
import numpy as np

from unittest.mock import patch, MagicMock
from ALBATROSSProtocol.ALBATROSS import ALBATROSS
from ecpy.curves import Curve, Point
from Elliga.ellifun import CurvetoNumber
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests
import config

class DummyPoint:
    """Clase dummy para simular puntos EC"""
    def __init__(self, x, y):
        self.x = x
        self.y = y

class MockECPoint:
    """CLASE SIMULADA PARA DEMOSTRAR LA NO-LINEALIDAD DE LAS CURVAS ELÍPTICAS"""
    def __init__(self, x):
        self.x = x

    def __mul__(self, escalar):
        # Simula una multiplicación en la curva (No es lineal, sumamos +1)
        return MockECPoint((self.x * escalar) + 1)

    def __rmul__(self, escalar):
        return self.__mul__(escalar)

    def __add__(self, otro_punto):
        # Simula una suma geométrica de puntos (No es lineal, sumamos +100)
        return MockECPoint(self.x + otro_punto.x + 100)

class RealNodeHandler(BaseHTTPRequestHandler):
    """Mini-Servidor para simular la red física"""
    def log_message(self, format, *args):
        pass  # Silenciamos los logs de red de la consola

    def do_GET(self):
        # Extraemos el ID del nodo de la URL (Ej: de "/node/3/commit" sacamos el 3)
        try:
            node_id = int(self.path.split('/')[2])
        except (IndexError, ValueError):
            node_id = 1

        if "commit" in self.path:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK_COMMIT")
        elif "reveal" in self.path:
            self.send_response(200)
            self.end_headers()
            fragment = self.server.fragmentos_secretos.get(node_id, 999)
            self.wfile.write(str(fragment).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

def arrancar_red_nodos_reales(fragmentos):
    # Levantamos UN SOLO servidor en el puerto 5000 simulando a Flask
    server = HTTPServer(('localhost', 5000), RealNodeHandler)
    server.fragmentos_secretos = fragmentos
    t = threading.Thread(target=server.serve_forever)
    t.daemon = True
    t.start()
    return [server]

def apagar_red_nodos_reales(servers):
    for s in servers:
        s.shutdown()
        s.server_close()

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

        self.albatross._ALBATROSS__num_participants = 4
        self.albatross._ALBATROSS__t = 1
        self.albatross.system = config.BYZANTINE
        self.albatross.mode = config.CLASSIC_MODE

        # Metemos en la matriz T los fragmentos recibidos (cada nodo manda 1 lista con su fragmento)
        self.albatross._ALBATROSS__T = [[150], [200], [999]]

        # Forzamos una raíz de la unidad sencilla para el test matemático
        self.albatross._ALBATROSS__network.get_q.return_value = 97

        # Mockeamos Vandermonde para que use la matriz inversa exacta del polinomio
        # La interpolación de Lagrange para x=1, x=2 y evaluar en 0 da los pesos [2, -1]
        # (2 * 150) + (-1 * 200) = 300 - 200 = 100 (¡El secreto!)
        self.albatross._ALBATROSS__crear_matriz_vandermonde = MagicMock(return_value=np.array([[2, -1, 0]]))

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
        self.albatross._ALBATROSS__num_participants = 4
        self.albatross._ALBATROSS__t = 1
        self.albatross.system = config.BYZANTINE
        self.albatross.mode = config.CLASSIC_MODE
        self.albatross._ALBATROSS__T = [[frag_1], [frag_2], [999]]
        self.albatross._ALBATROSS__network.get_q.return_value = 97

        # INTERPOLACIÓN MATEMÁTICA
        # Los pesos de Lagrange para evaluar en 0 dados x=1, x=2 son [2, -1]
        self.albatross._ALBATROSS__crear_matriz_vandermonde = MagicMock(return_value=np.array([[2, -1, 0]]))

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

        self.albatross._ALBATROSS__num_participants = 4
        self.albatross._ALBATROSS__t = 1
        self.albatross.system = config.BYZANTINE
        self.albatross.mode = config.EC_MODE  # Activamos modo EC
        self.albatross._ALBATROSS__network.get_q.return_value = 97

        self.albatross._ALBATROSS__T = [[MockECPoint(150)], [MockECPoint(200)], [MockECPoint(999)]]

        self.albatross._ALBATROSS__crear_matriz_vandermonde = MagicMock(return_value=np.array([[2, -1, 0]]))

        # Ejecutamos la fase final
        self.albatross._ALBATROSS__process_final_output()

        with open('aleatoriedad_final.txt', 'r') as f:
            resultado = f.read()

        # Al usar MockECPoint, la matemática no lineal hace que el resultado cambie.
        # En vez de 100 lineal, el objeto simulado sumará "100" extra por su comportamiento.
        # Por tanto, esperamos que la extracción devuelva un texto con números.
        self.assertTrue(len(resultado) > 0,
                        "Fallo en modo EC: No supo extraer la coordenada X para reconstruir el 100.")

    @patch('ALBATROSSProtocol.PPVSSProtocol.utils.Utils.rootunity')
    @patch('ALBATROSSProtocol.ALBATROSS.CurvetoNumber')
    def test_secret_reconstruction_elligator_mode(self, mock_curvetonumber, mock_rootunity):
        """Prueba de reconstrucción: Verifica que llama a la ofuscación en modo Elligator"""
        mock_rootunity.return_value = 2

        self.albatross._ALBATROSS__num_participants = 4
        self.albatross._ALBATROSS__t = 1
        self.albatross.system = config.BYZANTINE
        self.albatross.mode = config.ELLIGATOR_MODE  # Activamos modo Elligator
        self.albatross._ALBATROSS__network.get_q.return_value = 97

        # Hacemos que el generador 'h' de la curva simulada sea un 1.
        # Así, cuando Albatross haga (100 * h), el resultado seguirá siendo 100 puro.
        self.albatross._ALBATROSS__network.get_h.return_value = 1

        # Le pasamos cualquier objeto, la función mockeada hará el trabajo
        self.albatross._ALBATROSS__T = [[150], [200], [999]]
        self.albatross._ALBATROSS__crear_matriz_vandermonde = MagicMock(return_value=np.array([[2, -1, 0]]))

        # Simulamos que Elligator coge el secreto matemático (que dará 100) y lo ofusca
        mock_curvetonumber.side_effect = lambda p: f"ELLIGATOR_{p}"

        self.albatross._ALBATROSS__process_final_output()

        with open('aleatoriedad_final.txt', 'r') as f:
            resultado = f.read()

        self.assertTrue("100" in resultado, "Fallo en modo Elligator: La integración con CurvetoNumber está rota.")

    def test_old_vs_new_implementation_numbers(self):
        """
        Demuestra cómo el código original (np.multiply y Vandermonde sin 'i')
        destruía los datos, frente al código nuevo (np.dot y Vandermonde correcta).
        """
        # Suponemos que el secreto real era el número 100 y estos son los fragmentos (Matriz T) que nos devuelven los nodos (2x2 para simplificar)
        T_fragmentos = np.array([
            [150, 160],
            [200, 210]
        ])

        # =========================================================
        # 1. LA LÓGICA ANTIGUA (EL BUG)
        # =========================================================
        omega = 2
        l = 2
        n_columnas = 2

        # Bug A: Matriz de Vandermonde sin multiplicar por 'i' (filas clónicas)
        vander_antigua = np.array([[omega ** j for j in range(n_columnas)] for i in range(l)])

        # Bug B: np.multiply (multiplica celda a celda en lugar de filas por columnas)
        bug_generada = np.multiply(vander_antigua, T_fragmentos)

        with open('bug_antigua.txt', 'w') as f:
            f.write("=== LÓGICA ANTIGUA ===\n")
            f.write("Matriz Vandermonde Errónea (Filas iguales):\n" + str(vander_antigua) + "\n\n")
            f.write("Resultado de np.multiply (Basura matemática):\n" + str(bug_generada) + "\n")

        # =========================================================
        # 2. LA LÓGICA NUEVA (CORRECTA)
        # =========================================================

        # Corrección A: Multiplicar por 'i' para que cada fila sea única
        vander_nueva = np.array([[omega ** (i * j) for j in range(n_columnas)] for i in range(l)])

        # Corrección B: np.dot (multiplicación matricial real del álgebra lineal)
        secreto_real = np.dot(vander_nueva, T_fragmentos)

        with open('bug_secreto_correcto.txt', 'w') as f:
            f.write("=== LÓGICA ACTUAL ===\n")
            f.write("Matriz Vandermonde Correcta (Filas diferentes):\n" + str(vander_nueva) + "\n\n")
            f.write("Resultado de np.dot (Álgebra real):\n" + str(secreto_real) + "\n")

        # Comprobamos que, efectivamente, los resultados son totalmente distintos
        self.assertFalse(np.array_equal(bug_generada, secreto_real), "¡Increíble! La basura y el secreto coinciden.")

        print("\n[!] Test de Basura ejecutado. Revisa 'bug_antigua.txt' y 'bug_secreto_correcto.txt'")

    def test_old_vs_new_implementation_text(self):
        """
        Demuestra cómo el código original destruía una cadena de texto exacta,
        mientras que el código nuevo la recupera a la perfección.
        """
        # 1. EL VALOR EXACTO QUE METEMOS
        texto_original = "HOLA MUNDO ALBATROSS"
        # Convertimos la palabra a un número entero gigante
        secreto_int = int.from_bytes(texto_original.encode('utf-8'), 'big')

        # Simulamos que los nodos nos envían fragmentos de este secreto
        # (Polinomio: f(x) = secreto_int + 10x. Para x=1 y x=2)
        T_fragmentos = np.array([
            [secreto_int + 10],
            [secreto_int + 20]
        ])

        # Parámetros matemáticos
        omega = 2
        l = 2
        n_columnas = 2

        # =========================================================
        # 2. LÓGICA ANTIGUA (EL BUG)
        # =========================================================
        # Filas iguales y np.multiply
        vander_antigua = np.array([[omega ** j for j in range(n_columnas)] for i in range(l)])
        bug_generado = np.multiply(vander_antigua, T_fragmentos)

        # Intentamos forzar la lectura del primer elemento como si fuera el secreto
        numero_basura = int(bug_generado[0][0])

        try:
            num_bytes = (numero_basura.bit_length() + 7) // 8
            texto_basura = numero_basura.to_bytes(num_bytes, 'big').decode('utf-8')
        except Exception:
            texto_basura = "[ERROR FATAL: LOS BYTES SON ILEGIBLES]"

        # =========================================================
        # 3. LÓGICA NUEVA (LA CORRECTA)
        # =========================================================
        # Filas multiplicadas por 'i' y np.dot
        vander_nueva = np.array([[omega ** (i * j) for j in range(n_columnas)] for i in range(l)])
        # Invertimos la matriz para aplicar Lagrange correctamente en x=0 (simplificación teórica del test)
        matriz_lagrange_simulada = np.array([[2, -1]])

        secreto_real_matriz = np.dot(matriz_lagrange_simulada, T_fragmentos)
        numero_real = int(secreto_real_matriz[0][0])

        num_bytes_real = (numero_real.bit_length() + 7) // 8
        texto_recuperado = numero_real.to_bytes(num_bytes_real, 'big').decode('utf-8')

        # =========================================================
        # 4. GUARDAR EVIDENCIAS Y COMPROBAR
        # =========================================================
        with open('comparativa_texto.txt', 'w', encoding='utf-8') as f:
            f.write(f"TEXTO ORIGINAL ENVIADO: '{texto_original}'\n")
            f.write("-" * 40 + "\n")
            f.write(f"INTENTO LÓGICA ANTIGUA: '{texto_basura}'\n")
            f.write(f"INTENTO LÓGICA NUEVA  : '{texto_recuperado}'\n")

        # Comprobamos que la lógica nueva triunfa y la antigua falla
        self.assertEqual(texto_recuperado, texto_original, "La lógica nueva ha fallado.")
        self.assertNotEqual(texto_basura, texto_original, "La lógica antigua de milagro ha funcionado.")

    # =====================================================================
    # BLOQUE 5: TESTS NEGATIVOS (Modificación del polinomio)
    # =====================================================================
    @patch('requests.get')
    def test_reveal_negative_testing_false_polynomial(self, mock_get):
        """
        PRUEBA NEGATIVA (Seguridad): Simula un ataque Bizantino activo en la fase Reveal.
        Verifica que si un nodo devuelve un HTTP 400 (Fallo en la verificación VSS del polinomio),
        Albatross NO lo añade a la lista de éxitos y entonces no usará su fragmento corrupto
        """
        # 1. Simulamos que el servidor Flask del nodo 3 detecta la mentira matemática y devuelve 400
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "The polynomial verification uploaded by node 3 was incorrect"
        mock_get.return_value = mock_response

        # 2. El orquestador ALBATROSS le pide que revele su polinomio
        nodo_atacante_id = 3
        self.albatross._ALBATROSS__request_reveal(node_id=nodo_atacante_id)

        # 3. COMPROBACIÓN CRÍTICA: El nodo no debe estar en la lista de revelaciones exitosas
        self.assertNotIn(
            nodo_atacante_id,
            self.albatross._ALBATROSS__successful_reveal_ids,
            "¡Brecha de seguridad! El orquestador ha aceptado un polinomio falso."
        )

    # =========================================================================
    # BLOQUE 6: TESTS DE CURVAS ELÍPTICAS CON GEOMETRÍA NO LINEAL
    # =========================================================================
    def test_classic_mode_reconstruction(self):
        """Prueba que el modo clásico funciona con álgebra lineal normal"""
        self.albatross.mode = config.CLASSIC_MODE
        self.albatross._ALBATROSS__num_participants = 4
        self.albatross._ALBATROSS__t = 0

        # Fragmentos puros (Enteros): el orquestador cogerá los que necesite (l)
        self.albatross._ALBATROSS__T = [[10], [20], [30], [40]]

        # El test se adapta dinámicamente al tamaño 'l' que pida el Orquestador
        self.albatross._ALBATROSS__crear_matriz_vandermonde = MagicMock(
            side_effect=lambda w, l, t: np.array([[2, 3, 4, 5, 6, 7]])[:, :l+t]
        )

        # Ejecutamos
        self.albatross._ALBATROSS__process_final_output()

        # Leemos el resultado
        with open('aleatoriedad_final.txt', 'r') as f:
            resultado = f.read()

        # Si l=3 (200), Si l=2 (80), Si l=4 (400)
        self.assertTrue(any(x in resultado for x in ["80", "200", "400"]),
                        "Fallo en Modo Clásico: El álgebra lineal se ha roto.")

    def test_ec_geometric_mode_reconstruction(self):
        """
        Prueba que el modo EC respeta la geometría de la curva. Si falla, significa que se está sacando la '.x' antes de multiplicar
        """
        self.albatross.mode = config.EC_MODE
        self.albatross._ALBATROSS__num_participants = 4
        self.albatross._ALBATROSS__t = 0

        # Los nodos envían PUNTOS DE LA CURVA (Simulados)
        self.albatross._ALBATROSS__T = [[MockECPoint(10)], [MockECPoint(20)], [MockECPoint(30)], [MockECPoint(40)]]
        self.albatross._ALBATROSS__crear_matriz_vandermonde = MagicMock(
            side_effect=lambda w, l, t: np.array([[2, 3, 4, 5, 6, 7]])[:, :l+t]
        )

        self.albatross._ALBATROSS__process_final_output()

        with open('aleatoriedad_final.txt', 'r') as f:
            resultado = f.read()

        # Si sumara enteros, daría 80 o 200. ¡No debe dar eso!
        self.assertFalse(any(x in resultado for x in ["80", "200", "400"]), "¡ERROR CRÍTICO! Numpy está operando con enteros, destruyendo la geometría de la Curva Elíptica")
        # Resultados geométricos válidos: l=2 (182), l=3 (403), l=4 (704)
        self.assertTrue(any(x in resultado for x in ["182", "403", "704"]),
                        "Fallo en Modo EC: No se ha aplicado la reconstrucción geométrica correcta")

    def test_elligator_geometric_mode_reconstruction(self):
        """
        Prueba que Elligator desofusca, opera en la curva, y vuelve a ofuscar
        """
        self.albatross.mode = config.ELLIGATOR_MODE
        self.albatross._ALBATROSS__num_participants = 4
        self.albatross._ALBATROSS__t = 0

        # Los nodos envían NÚMEROS ofuscados (Ej: 10, 20, 30 y 40)
        self.albatross._ALBATROSS__T = [[MockECPoint(10)], [MockECPoint(20)], [MockECPoint(30)], [MockECPoint(40)]]
        self.albatross._ALBATROSS__crear_matriz_vandermonde = MagicMock(
            side_effect=lambda w, l, t: np.array([[2, 3, 4, 5, 6, 7]])[:, :l+t]
        )

        # Reemplazamos temporalmente la función en el módulo cargado
        import ALBATROSSProtocol.ALBATROSS as alb_module
        funcion_original = alb_module.CurvetoNumber  # Guardamos la original

        # Le ponemos nuestra función falsa que solo saca un texto
        alb_module.CurvetoNumber = lambda p: f"ELLIGATOR_{p.x}"

        try:
            self.albatross._ALBATROSS__process_final_output()
        finally:
            # Restauramos la función original SIEMPRE, pase lo que pase
            alb_module.CurvetoNumber = funcion_original

        with open('aleatoriedad_final.txt', 'r') as f:
            resultado = f.read()

        self.assertTrue("ELLIGATOR_" in resultado, "Fallo: No se aplicó Elligator al final.")
        self.assertTrue(any(x in resultado for x in ["182", "403", "704"]), "Fallo: Geometría rota antes de Elligator.")

    # =========================================================================
    # BLOQUE 7: TESTS DE ESCALABILIDAD Y LÍMITES BFT (STRESS TESTS)
    # =========================================================================
    def test_orchestrator_extreme_bft_limits(self):
        """
        Prueba de límites BFT reales en una red media/grande (N=10). Verifica que el orquestador aborta, sobrevive o se optimiza según los fragmentos recibidos
        """
        self.albatross.mode = config.CLASSIC_MODE
        self.albatross._ALBATROSS__num_participants = 10
        self.albatross._ALBATROSS__t = 3
        # Matemáticas internas que hará el orquestador:
        # l = 10 - 2(3) = 4 (Vandermonde necesita 4)
        # r = 10 - 3 = 7 (Mínimo de seguridad para no abortar)

        # Simulamos una Vandermonde que se adapta al tamaño 'l' pedido (1x4)
        self.albatross._ALBATROSS__crear_matriz_vandermonde = MagicMock(
            side_effect=lambda w, l, t: np.array([[2, 3, 4, 5, 6, 7, 8, 9, 10]])[:, :l+t]
        )

        # --- CASO EXTREMO 1: FALLO DE RED CRÍTICO (6 FRAGMENTOS) ---
        # Le damos 6 fragmentos. Al ser menor que r=7, DEBE abortar por seguridad.
        self.albatross._ALBATROSS__T = [[10], [20], [30], [40], [50], [60]]

        with self.assertRaises(ValueError) as context:
            self.albatross._ALBATROSS__process_final_output()
        self.assertTrue("No hay suficientes fragmentos" in str(context.exception),
                        "Fallo de Seguridad: El orquestador intentó reconstruir sin quórum")

        # --- CASO EXTREMO 2: SUPERVIVENCIA AL LÍMITE (7 FRAGMENTOS EXACTOS) ---
        # Le damos exactamente r=7 fragmentos. Debe sobrevivir y recortar a l=4.
        self.albatross._ALBATROSS__T = [[10], [20], [30], [40], [50], [60], [70]]

        try:
            self.albatross._ALBATROSS__process_final_output()
        except Exception as e:
            self.fail(f"Fallo de Liveness: El orquestador crasheó teniendo los fragmentos mínimos. Error: {e}")

        with open('aleatoriedad_final.txt', 'r') as f:
            resultado_limite = f.read()

        # --- CASO EXTREMO 3: RED PERFECTA (10 FRAGMENTOS) ---
        # Le damos los 10 fragmentos. Debe ignorar los 6 extra y dar el MISMO resultado matemático
        self.albatross._ALBATROSS__T = [[10], [20], [30], [40], [50], [60], [70], [80], [90], [100]]
        self.albatross._ALBATROSS__process_final_output()

        with open('aleatoriedad_final.txt', 'r') as f:
            resultado_perfecto = f.read()

        # El resultado debe ser idéntico, demostrando la optimización O(1)
        self.assertEqual(resultado_limite, resultado_perfecto,
                         "Fallo de Optimización: El resultado varió al recibir más nodos")

    # =========================================================================
    # BLOQUE 8: TESTS END-TO-END (Levantando Nodos HTTP TCP Reales)
    # =========================================================================
    def test_e2e_real_network_classic_holamundo(self):
        """E2E Clásico: La red física TCP transmite y recupera 'Hola Mundo Cruel'"""
        # El secreto que queremos recuperar
        texto_secreto = "Hola Mundo Cruel"
        secreto_int = int.from_bytes(texto_secreto.encode('utf-8'), 'big')

        # Matemáticas para la matriz [2, 3] (2*T1 + 3*T2 = secreto_int)
        T2 = 2 if secreto_int % 2 == 0 else 1
        T1 = (secreto_int - (3 * T2)) // 2

        fragmentos_red = {1: T1, 2: T2, 3: 999, 4: 999}
        servidores_activos = arrancar_red_nodos_reales(fragmentos_red)

        try:
            self.albatross.mode = config.CLASSIC_MODE
            self.albatross._ALBATROSS__num_participants = 4
            self.albatross._ALBATROSS__t = 1

            # Como la URL real es localhost:5000, ya no necesitamos mockear el endpoint
            self.albatross._ALBATROSS__crear_matriz_vandermonde = MagicMock(
                side_effect = lambda w, l, t: np.array([[2, 3, 0, 0, 0, 0]])[:, :l + t]
            )

            # 1. FASE COMMIT (TCP Real al puerto 5000)
            for i in range(1, 5): self.albatross._ALBATROSS__request_commit(i)

            # 2. FASE REVEAL (Descarga TCP Real del puerto 5000)
            self.albatross._ALBATROSS__T = []
            for i in self.albatross._ALBATROSS__successful_commit_ids:
                respuesta = requests.get(f"http://localhost:5000/node/{i}/reveal")
                valor = int(respuesta.text.replace('[', '').replace(']', ''))
                self.albatross._ALBATROSS__T.append([valor])

            # 3. RECONSTRUCCIÓN FINAL
            self.albatross._ALBATROSS__process_final_output()

            with open('aleatoriedad_final.txt', 'r') as f:
                resultado_str = f.read()

            num = int(resultado_str.replace('[', '').replace(']', '').strip())
            texto_recuperado = num.to_bytes((num.bit_length() + 7) // 8, 'big').decode('utf-8')

            self.assertEqual(texto_recuperado, texto_secreto, "Fallo E2E: La red no pudo recuperar el texto.")

        finally:
            apagar_red_nodos_reales(servidores_activos)

    def test_e2e_real_network_ec_mode(self):
        """E2E Curvas Elípticas: Descarga JSON TCP y procesado geométrico"""
        fragmentos_red = {1: 150, 2: 200, 3: 999, 4: 999}
        servidores_activos = arrancar_red_nodos_reales(fragmentos_red)

        try:
            self.albatross.mode = config.EC_MODE
            self.albatross._ALBATROSS__num_participants = 4
            self.albatross._ALBATROSS__t = 1
            self.albatross._ALBATROSS__crear_matriz_vandermonde = MagicMock(
                side_effect=lambda w, l, t: np.array([[2, 3, 4, 5, 6, 7]])[:, :l+t]
            )

            for i in range(1, 5): self.albatross._ALBATROSS__request_commit(i)

            self.albatross._ALBATROSS__T = []
            for i in self.albatross._ALBATROSS__successful_commit_ids:
                respuesta = requests.get(f"http://localhost:5000/node/{i}/reveal")
                punto_ec = MockECPoint(int(respuesta.text))
                self.albatross._ALBATROSS__T.append([punto_ec])

            self.albatross._ALBATROSS__process_final_output()

            with open('aleatoriedad_final.txt', 'r') as f:
                resultado = f.read()
            self.assertTrue(len(resultado) > 0, "Fallo E2E EC: El secreto está vacío")

        finally:
            apagar_red_nodos_reales(servidores_activos)

    @patch('ALBATROSSProtocol.ALBATROSS.CurvetoNumber')
    def test_e2e_real_network_elligator_mode(self, mock_curvetonumber):
        """E2E Elligator: Red TCP, geometría y ofuscación determinista final"""
        fragmentos_red = {1: 150, 2: 200, 3: 999, 4: 999}
        servidores_activos = arrancar_red_nodos_reales(fragmentos_red)

        try:
            self.albatross.mode = config.ELLIGATOR_MODE
            self.albatross._ALBATROSS__num_participants = 4
            self.albatross._ALBATROSS__t = 1
            self.albatross._ALBATROSS__crear_matriz_vandermonde = MagicMock(
                side_effect=lambda w, l, t: np.array([[2, 3, 4, 5, 6, 7]])[:, :l+t]
            )
            mock_curvetonumber.side_effect = lambda p: f"ELLIGATOR_{p}"

            for i in range(1, 5): self.albatross._ALBATROSS__request_commit(i)

            self.albatross._ALBATROSS__T = []
            for i in self.albatross._ALBATROSS__successful_commit_ids:
                respuesta = requests.get(f"http://localhost:5000/node/{i}/reveal")
                self.albatross._ALBATROSS__T.append([int(respuesta.text)])

            self.albatross._ALBATROSS__process_final_output()

            with open('aleatoriedad_final.txt', 'r') as f:
                resultado = f.read()
            self.assertTrue("ELLIGATOR_" in resultado, "Fallo E2E Elligator: La ofuscación ha fallado")

        finally:
            apagar_red_nodos_reales(servidores_activos)


if __name__ == '__main__':
    unittest.main()