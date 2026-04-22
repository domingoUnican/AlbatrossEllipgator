import unittest
from unittest.mock import patch, MagicMock
import config

from ALBATROSSProtocol.ALBATROSS import ALBATROSS

class TestProtocolTheory(unittest.TestCase):

    def setUp(self):
        """Instanciamos la clase de verdad, pero simulamos la red HTTP"""
        self.network_mock = MagicMock()
        # N = 10, Bizantino (t = 3) -> Necesitamos al menos 7 respuestas correctas para que el protocolo avance.
        self.albatross = ALBATROSS(self.network_mock, num_participants=10, system=config.BYZANTINE,
                                   mode=config.CLASSIC_MODE)

    @patch('requests.get')
    def test_commit_phase_theoretical_threshold(self, mock_get):
        """
        La fase Commit se considera válida si y solo si al menos (N - t) nodos completan
        el commit y publican sus compromisos polinomiales g^{f(x)}.
        """
        # Simulamos que los 10 nodos responden OK (HTTP 200)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        self.albatross.execute_commit_phase()

        # Como quitamos el tope para evitar timeouts, ahora sí se guardan los 10
        self.assertEqual(len(self.albatross._ALBATROSS__successful_commit_ids), 10)

    @patch('requests.get')
    def test_reveal_phase_triggers_recovery(self, mock_get):
        """
        Si en la fase Reveal, el número de verificaciones exitosas de los polinomios
        (f(i) concuerda con g^{f(i)}) es menor que N - t, el protocolo no puede reconstruir
        de forma directa y DEBE ir a la fase de Recovery.
        """
        # Preparamos el estado como si 7 nodos hubieran hecho commit
        self.albatross._ALBATROSS__successful_commit_ids = {0, 1, 2, 3, 4, 5, 6}

        # Simulamos la red para el Reveal: 4 responden OK, 3 fallan (por error de validación del polinomio)
        def mock_reveal_network(url):
            resp = MagicMock()
            # Si la URL contiene el nodo 0, 1, 2 o 3, devolvemos 200. Si no, 400 (Fallo VSS).
            if any(f"node/{i}/reveal" in url for i in [0, 1, 2, 3]):
                resp.status_code = 200
            else:
                resp.status_code = 400
            return resp

        mock_get.side_effect = mock_reveal_network

        self.albatross.execute_reveal_phase()

        # Verificamos que solo 4 pasaron la validación teórica de los compromisos
        self.assertEqual(len(self.albatross._ALBATROSS__successful_reveal_ids), 4)

        # 3. Simulamos qué hace el protocolo cuando llamamos a Output
        # Como 4 < 7 (umbral), debería ir por la rama de recovery
        # Mockeamos __execute_recovery_phase para ver si la llama
        self.albatross._ALBATROSS__execute_recovery_phase = MagicMock()

        self.albatross.handle_output_phase()

        # El protocolo debe darse cuenta de la falta de quorum y llamar a recuperación
        self.albatross._ALBATROSS__execute_recovery_phase.assert_called_once()

    @patch('requests.get')
    def test_reconstruction_fails_if_byzantine_threshold_broken(self, mock_get):
        """
        Testeamos la tolerancia a fallos. Si el número de nodos corruptos (que mintieron en VSS)
        supera la capacidad teórica t de corrección de errores de la matriz de Vandermonde,
        la reconstrucción es imposible.
        """
        self.albatross._ALBATROSS__successful_commit_ids = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9}

        # Simulamos que 6 nodos sanos revelaron, y 4 cayeron (fueron maliciosos)
        # N=10, t=3. Tenemos 4 maliciosos -> Rompe la tolerancia a fallos
        self.albatross._ALBATROSS__successful_reveal_ids = {0, 1, 2, 3, 4, 5}
        failed_nodes = {6, 7, 8, 9}

        # Debemos asegurar que el orquestador aborta, porque matemáticamente es imposible
        with self.assertRaises(ValueError) as context:
            self.albatross._ALBATROSS__execute_reconstruction_phase(failed_nodes)

        self.assertTrue("Imposible recuperar" in str(context.exception))


if __name__ == '__main__':
    unittest.main()