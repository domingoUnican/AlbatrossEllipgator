import random
import threading 
import time
import numpy as np
import requests
import sys

import config

from .Elliga.ellifun import CurvetoNumber
from .PPVSSProtocol.utils import Utils

class ALBATROSS:
    def __init__(self, network, num_participants, system, mode):
        """Initializes ALBATROSS protocol with given network and number of participants."""
        self.__network = network
        self.__num_participants = num_participants
        self.mode = mode  # Guardamos el modo ("classic", "ec" o "elligator")
        # t es el umbral máximo de participantes maliciosos: bizantino max 1/3, mayoría (Caso peor: 51%buenos), caso mejor 100% buenos
        if system == config.BYZANTINE:
            self.__t = (num_participants - 1) // 3
            self.system = config.BYZANTINE
        elif system == config.ABSOLUTE_MAJORITY:
            self.__t = (num_participants - 1) // 2
            self.system = config.ABSOLUTE_MAJORITY
        else:
            print("Error al inicializar el umbral máximo __t en Albatross")
            exit(0)
        self.__successful_commit_ids = set()
        self.__successful_reveal_ids = set()
        self.__successful_recovery_ids = set()
        self.__T = {} # Uso de diccionario

    def __request_commit(self, node_id):
        """Sends a commit request to the node and adds the node to successful commits if successful."""
        try:
            response = requests.get(f"http://localhost:5000/node/{node_id}/commit")
            # Cogemos todos pq un malicioso va a dar también 200
            if response.status_code == 200:
                self.__successful_commit_ids.add(node_id)
                print(f"Commit successful on node {node_id}: {response.text}")
            else:
                print(f"Commit failed on node {node_id}: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Error during commit on node {node_id}: {e}")

    def __request_reveal(self, node_id):
        """Sends a reveal request to the node and adds the node to successful reveals if successful."""
        try:
            response = requests.get(f"http://localhost:5000/node/{node_id}/reveal")
            # Cogemos todos pq un malicioso va a dar también 200
            if response.status_code == 200:
                self.__successful_reveal_ids.add(node_id)
                print(f"Reveal successful on node {node_id}: {response}")
            else:
                print(f"Reveal failed on node {node_id}: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Error during reveal on node {node_id}: {e}")

    def __request_output(self, node_id):
        """Sends a request to extract randomness from the node and appends the result."""
        try:
            response = requests.get(f"http://localhost:5000/node/{node_id}/output")
            # Cogemos todos pq un malicioso va a dar también 200
            if response.status_code == 200:
                json_response = response.json()
                decoded_response = json_response.get('result', [])
                # Parseamos la base 16 (hexadecimal), el if para que sea compatible con test unitarios antiguos en base 10
                numbers = [int(x, 16) if isinstance(x, str) and x.startswith('0x') else int(x) for x in
                           decoded_response]
                self.__T[node_id] = numbers
                print("Number of secrets post-add:", len(self.__T.keys()))
                print(f"Randomness extraction successful on node {node_id}")
            else:
                print(f"Output request failed on node {node_id}: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Error during output request on node {node_id}: {e}")

    def __request_recovery(self, node_id, failed_nodes):
        """Sends a recovery request to the node in case some nodes failed."""
        try:
            failed_nodes_str = ','.join(map(str, failed_nodes))
            response = requests.get(f"http://localhost:5000/node/{node_id}/recovery?failed_nodes={failed_nodes_str}")
            # Cogemos todos pq un malicioso va a dar también 200
            if response.status_code == 200:
                self.__successful_recovery_ids.add(node_id)
                print(f"Recovery successful on node {node_id}")
            else:
                print(f"Recovery failed on node {node_id}: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Error during recovery request on node {node_id}: {e}")
    
    def __request_reconstruction(self, reco_id, node_id, reco_parties):
        """Sends a reconstruction request to the node with the given reconstruction parties."""
        try:
            reco_part = ','.join(map(str, reco_parties))
            response = requests.get(f"http://localhost:5000/node/{reco_id}/reconstruction/{node_id}?reco_parties={reco_part}")
            # Cogemos todos pq un malicioso va a dar también 200
            if response.status_code == 200:
                json_response = response.json()
                decoded_response = json_response.get('result', [])
                numbers = [int(x, 16) if isinstance(x, str) and x.startswith('0x') else int(x) for x in decoded_response]
                self.__T[node_id] = numbers
                print("Number of secrets post-add:", len(self.__T.keys()))



                print(f"Reconstruction successful for node {node_id}")
            else:
                print(f"Reconstruction failed for node {node_id}: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Error during reconstruction request on node {node_id}: {e}")




    def execute_commit_phase(self):
        """Executes the commit phase by sending commit requests to all participants."""
        start_time = time.time()
        threads = []
        print("Executing commit requests...")
        for i in range(self.__num_participants):
            thread = threading.Thread(target=self.__request_commit, args=(i,))
            threads.append(thread)
            thread.start()
        for thread in threads:
            thread.join()
        end_time = time.time()
        return end_time - start_time

    def execute_reveal_phase(self):
        """Executes the reveal phase by sending reveal requests to all successfully committed nodes."""
        start_time = time.time()
        threads = []
        print("Executing reveal requests...")
        for node_id in self.__successful_commit_ids:
            thread = threading.Thread(target=self.__request_reveal, args=(node_id,))
            threads.append(thread)
            thread.start()
        for thread in threads:
            thread.join()
        end_time = time.time()
        return end_time - start_time

    def handle_output_phase(self):
        """Handles the output phase by either processing the output or executing the recovery phase."""
        start_time = time.time()
        if len(self.__successful_reveal_ids) >= (self.__num_participants - self.__t):
            print("Threshold reached: Enough reveals were successful")
            self.__process_output()
            end_time = time.time()
            return end_time - start_time
        else:
            print("Some reveals failed. Proceeding with alternative action")
            self.__execute_recovery_phase()
            end_time = time.time()
            return end_time - start_time

    def __process_output(self):
        """Processes the output by sending output requests to all successfully revealed nodes"""
        threads = []

        r = self.__num_participants - self.__t

        # Cogemos solo los primeros 'r' nodos sanos
        nodos_necesarios = list(self.__successful_reveal_ids)[:r]

        for node_id in self.__successful_reveal_ids:
            thread = threading.Thread(target=self.__request_output, args=(node_id,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        self.__process_final_output()

    def __process_final_output(self):
        """Processes the final output by reconstructing the secret using Vandermonde matrix and randomness."""

        if not self.__T or len(self.__T) == 0:
            raise ValueError(
                "Fallo crítico: Ningún nodo devolvió fragmentos en la fase de Output. La red está vacía. Revisa la conexión HTTP.")

        # Cogemos cualquier fragmento que exista en el diccionario para ver su longitud
        any_fragment = next(iter(self.__T.values()))
        w = Utils.rootunity(len(any_fragment), self.__network.get_q())

        t = self.__num_participants // 3

        if self.system == config.BYZANTINE:
            l = self.__num_participants - 2 * t # Tamaño Matemático: número de coeficientes exactos que tiene tu matriz de Vandermonde
            r = self.__num_participants - t # Mínimo de Supervivencia: número de fragmentos que necesitas como mínimo para que la red no aborte
        elif self.system == config.ABSOLUTE_MAJORITY:
            l = max(1, self.__num_participants - t)
            r = t + 1
        else:
            raise ValueError("Modo inválido. Usa 'bizantino' o 'mayoria'.")

        if l <= 0:
            raise ValueError(f"Parámetros inválidos: l={l}. Ajusta t para que l > 0.")

        matriz_vander = self.__crear_matriz_vandermonde(w, l, t)
        print("Vandermonde matrix size:", matriz_vander.shape)

        # Comprobamos el tamaño de la matriz de Vandermore para si hace falta, parar ya y que no haga algo incorrecto
        if len(self.__T) < r:
            raise ValueError(f"No hay suficientes fragmentos ({len(self.__T)}) para reconstruir (se necesitan {r}).")

        # Cogemos exactamente los primeros 'r' fragmentos: más rápido que cogerlos aleatorios e igual de válido
        # de la matriz de Vandermonde (que dicta el tamaño: (l, r)) para que el np.dot encaje perfecto
        #T_recortada = self.__T[:r]

        # 1. Obtenemos los IDs ordenados matemáticamente
        nodos_necesarios = sorted(list(self.__successful_reveal_ids))[:r]

        # 2. Alineamos Vandermonde con los IDs exactos
        if not isinstance(matriz_vander, np.ndarray):
            matriz_vander = np.array(matriz_vander)
        matriz_vander = matriz_vander[:, nodos_necesarios]

        # 3. Extraemos fragmentos en el orden estricto de Vandermonde
        T_recortada = [self.__T[nid] for nid in nodos_necesarios]

        # 3. Extraemos fragmentos en el orden estricto de Vandermonde
        # dtype=object respeta tanto el álgebra lineal normal (enteros) como la geometría no lineal (Puntos de la curva)
        # Forzamos una matriz de tamaño (r, 1) y metemos los objetos uno a uno para que Numpy NO desempache las coordenadas (x, y) de los Puntos EC
        matriz_T = np.empty((len(T_recortada), 1), dtype=object)

        # 4. Forzamos matriz protegiendo EC
        for i, fragmento in enumerate(T_recortada):
            # Si el fragmento viene anidado en una lista [[Punto]], lo extraemos
            item = fragmento[0] if isinstance(fragmento, list) else fragmento
            matriz_T[i, 0] = item

        print("Matrix T size:", matriz_T.shape)

        # Vandermonde (l, r) * matriz_T (r, 1) = Resultado (l, 1)
        aleatoriedad = self.__multiplicar_matrices(matriz_vander, matriz_T)

        # Extracción del valor final
        aleatoriedad_final = []
        for punto_reconstruido in aleatoriedad.flatten():
            if self.mode == config.CLASSIC_MODE:
                aleatoriedad_final.append(punto_reconstruido)
            else:
                # El orquestador recibe escalares (ints)
                # Para obtener el Punto Geométrico, multiplicamos el escalar por el generador de la curva
                if isinstance(punto_reconstruido, int) or type(punto_reconstruido).__name__.startswith('int'):
                    punto_EC = punto_reconstruido * self.__network.get_h()
                else:
                    punto_EC = punto_reconstruido

                if self.mode == config.ELLIGATOR_MODE:
                    aleatoriedad_final.append(CurvetoNumber(punto_EC))
                elif self.mode == config.EC_MODE:
                    aleatoriedad_final.append(punto_EC.x)

        print("Final output size:", len(aleatoriedad_final))
        print("Secret reconstruction completed.")

        with open('aleatoriedad_final.txt', 'w') as archivo:
            # Convertimos cada número de la lista a hexadecimal si 'n' es un número entero. Si ya es string (Elligator), lo dejamos intacto.
            lista_hex = [hex(n) if isinstance(n, int) else str(n) for n in aleatoriedad_final]
            # Guardamos la lista de strings hexadecimales
            archivo.write(str(lista_hex))
        return

    def __execute_recovery_phase(self):
        """Executes the recovery phase to recover failed nodes."""
        threads = []
        failed_nodes = self.__successful_commit_ids - self.__successful_reveal_ids 

        for node_id in range(self.__num_participants):
            thread = threading.Thread(target=self.__request_recovery, args=(node_id, failed_nodes))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        if len(self.__successful_recovery_ids) >= (self.__num_participants - self.__t):
            print("Proceeding with secret reconstruction.")
            self.__execute_reconstruction_phase(failed_nodes)
        else:
            print("Cannot reconstruct secret, insufficient number of well-intentioned participants.")
            exit(-1)

    def __execute_reconstruction_phase(self, failed_nodes):
        """Executes the reconstruction phase by gathering output from successfully revealed nodes and calculating the final output."""
        if len(failed_nodes) > self.__t:
            raise ValueError(
                f"Fallo crítico: Hay {len(failed_nodes)} nodos caídos, pero el umbral máximo es {self.__t}. Imposible recuperar.")

        threads = []

        # Pedir el output a los nodos que se revelaron correctamente
        for node_id in self.__successful_reveal_ids:
            thread = threading.Thread(target=self.__request_output, args=(node_id,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        t = self.__t

        if self.system == config.BYZANTINE:
            l = self.__num_participants - 2 * t
            r = self.__num_participants - t
        elif self.system == config.ABSOLUTE_MAJORITY:
            l = max(1, self.__num_participants - t)
            r = t + 1
        else:
            raise ValueError("Sistema no reconocido")

        # Solo cogemos nodos que sabemos 100% que están vivos y revelaron bien
        successful_reveal_participants = list(self.__successful_reveal_ids.copy())
        if len(successful_reveal_participants) < r:
            raise ValueError(
                f"No hay suficientes nodos sanos ({len(successful_reveal_participants)}) para pedir reconstrucción (se necesitan {r}).")

        for node_id in failed_nodes:
            # Choose reconstruction parties
            subgrupo = random.sample(successful_reveal_participants, r)

            thread = threading.Thread(target=self.__request_reconstruction, args=(node_id, subgrupo[0], subgrupo))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()

        # Convert the matrix to h^s elements
        print("Number of secrets:", len(self.__T))
        for lista in self.__T.values():
            for i in range(len(lista)):
                if self.__network.EC:
                    lista[i]= lista[i]*self.__network.h
                else:
                    lista[i] = pow(self.__network.h, lista[i], self.__network.p)

        # Cogemos cualquier fragmento que exista en el diccionario para ver su longitud
        any_fragment = next(iter(self.__T.values()))
        # Create Vandermonde matrix with w.
        w = Utils.rootunity(len(any_fragment), self.__network.get_q())

        matriz_vander = self.__crear_matriz_vandermonde(w, l, t)
        print("Vandermonde matrix size:", matriz_vander.shape)
        print(self.__T)

        # Convertimos la lista de supervivientes y fallados a lista normal ya que es un set() para trabajar com Numpy y la ordenamos
        indices_sanos = sorted(list(self.__successful_reveal_ids) + failed_nodes)

        # Extraemos los fragmentos desempaquetando las listas anidadas
        fragmentos_ordenados = []
        for nid in indices_sanos:
            frag = self.__T[nid]
            item = frag[0] if isinstance(frag, list) else frag
            fragmentos_ordenados.append([item])

        # Creamos la matriz T respetando el modo criptográfico
        if self.mode == config.ELLIGATOR_MODE or self.mode == config.EC_MODE:
            matriz_T = np.array(fragmentos_ordenados, dtype=object)
        elif self.mode == config.CLASSIC_MODE:
            matriz_T = np.array(fragmentos_ordenados)
        else:
            raise ValueError("Modo inválido. Usa 'ec', 'elligator' o 'classic'.")

        print("Matrix T size:", matriz_T.shape)

        # Seleccionamos SOLO las columnas de los nodos que sobrevivieron para alinear perfectamente la matemática de Vandermonde con los fragmentos recibidos
        if not isinstance(matriz_vander, np.ndarray):
            matriz_vander = np.array(matriz_vander)

        matriz_vander = matriz_vander[:, indices_sanos]

        # 2. Multiplicamos directamente (Sin transponer)
        aleatoriedad_bruta = self.__multiplicar_matrices(matriz_vander, matriz_T)

        # 3. Extraemos la X o aplicamos elligator sol oal final
        aleatoriedad_final = []
        for resultado in aleatoriedad_bruta.flatten():
            if self.mode == config.CLASSIC_MODE:
                aleatoriedad_final.append(resultado)
            elif self.mode == config.ELLIGATOR_MODE:
                aleatoriedad_final.append(CurvetoNumber(resultado))
            elif self.mode == config.EC_MODE:
                aleatoriedad_final.append(resultado.x)  # Extracción de X al final

        # Guardar el contenido de aleatoriedad_final en un archivo .txt
        with open('aleatoriedad_final.txt', 'w') as archivo:
            lista_hex = [hex(n) if isinstance(n, int) else str(n) for n in aleatoriedad_final]
            archivo.write(str(lista_hex))

        print("Secret reconstruction completed.")

    def __crear_matriz_vandermonde(self, omega, l, t):
        """
        Creates a Vandermonde matrix of size (l, num_participants).
        """
        # Debe haber una columna por cada posible participante para poder alinear el ID
        n_columnas = self.__num_participants
        return np.array([[omega ** (i * j) for j in range(n_columnas)] for i in range(l)])

    def __multiplicar_matrices(self, matriz_a, matriz_b):
        """
        Multiplies two matrices of the same size.
        """
        return np.dot(matriz_a, matriz_b)
