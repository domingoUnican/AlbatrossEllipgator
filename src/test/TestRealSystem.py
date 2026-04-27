import unittest
import config

from main import create_network, start_flask_server
from ALBATROSSProtocol.ALBATROSS import ALBATROSS


class TestSistemaRealE2E(unittest.TestCase):

    def test_flujo_completo_arquitectura_real(self):
        """
        Levanta Flask y la red con los métodos reales de main.py,
        ejecuta el protocolo entero y válida que se genera el secreto
        """
        # 1. Parámetros BFT (bizantinos) mínimos reales
        participantes = 4
        maliciosos = 1

        print("\n[+] Inicializando Network y claves reales...")
        # Llama a tu función real en main.py
        network = create_network(participantes, maliciosos, EC=False)

        print("[+] Levantando Flask Server en el puerto 5000 (Hilo de fondo)...")
        # Llama a tu función real en main.py que devuelve el hilo
        server_thread = start_flask_server(network)

        try:
            print("[+] Arrancando Orquestador ALBATROSS...")
            protocol = ALBATROSS(network, participantes, config.BYZANTINE, config.CLASSIC_MODE)

            # 2. EJECUCIÓN FÍSICA DEL PROTOCOLO (Con red y polinomios reales)
            print(" -> Fase de Commit...")
            protocol.execute_commit_phase()

            print(" -> Fase de Reveal...")
            protocol.execute_reveal_phase()

            print(" -> Fase de Reconstrucción (Output)...")
            protocol.handle_output_phase()

            # 3. VALIDACIÓN
            with open('aleatoriedad_final.txt', 'r') as f:
                resultado = f.read()

            # Como aplicamos criptografía real con ruido aleatorio, no podemos buscar algo en concreto,
            # así que comprobamos que el archivo no está vacío, para saber si el protocolo hizo su trabajo matemático y TCP
            self.assertTrue(len(resultado) > 5,
                            "Fallo Crítico: El sistema real no generó el secreto o el archivo está vacío.")
            print(
                f"\n[+] ¡Éxito Total! El sistema real (Flask + PPVSS) completó el ciclo y generó el secreto: {resultado[:20]}...")

        except Exception as e:
            self.fail(f"La arquitectura real ha crasheado en tiempo de ejecución: {e}")

        finally:
            # 4. LIMPIEZA OBLIGATORIA
            print("\n[+] Apagando servidor Flask de forma segura...")
            server_thread.shutdown()
            server_thread.join()


if __name__ == '__main__':
    unittest.main()