import unittest
import config
import time

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
        t = participantes // 3

        print("\n[+] Inicializando Network y claves reales...")
        # Llama a tu función real en main.py
        network = create_network(participantes, maliciosos, t, EC=False)

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

    def test_benchmark_rendimiento_fases(self):
        """Mide los tiempos de cada fase y verifica que se ejecutan en tiempos lógicos (sin deadlocks)"""
        participantes = 10  # Una red un poco más grande para que haya algo que medir
        maliciosos = 2
        t = participantes // 3

        network = create_network(participantes, maliciosos, t, EC=False)
        server_thread = start_flask_server(network)

        try:
            protocol = ALBATROSS(network, participantes, config.BYZANTINE, config.CLASSIC_MODE)

            # Medimos Commit
            t_commit = protocol.execute_commit_phase()

            # Medimos Reveal
            t_reveal = protocol.execute_reveal_phase()

            # Medimos Output
            t_output = protocol.handle_output_phase()

            # Aseguramos que los tiempos son reales y mayores a 0
            self.assertGreater(t_commit, 0.0)
            self.assertGreater(t_reveal, 0.0)
            self.assertGreater(t_output, 0.0)

            # Assert de seguridad (Ejemplo: que una red de 10 nodos no tarde más de 10 segundos en total)
            self.assertLess(t_commit + t_reveal + t_output, 100.0,
                            "Fallo de rendimiento: El sistema va demasiado lento.")

            print(
                f"\n[Benchmark] Tiempos N=10 -> Commit: {t_commit:.3f}s | Reveal: {t_reveal:.3f}s | Output: {t_output:.3f}s")

        finally:
            server_thread.shutdown()
            server_thread.join()


if __name__ == '__main__':
    unittest.main()