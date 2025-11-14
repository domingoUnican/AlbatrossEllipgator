import argparse
import sys
import threading
import time
import signal

from sympy.physics.units import minutes

from DistributedNetwork.NetworkManagement.network import Network
from DistributedNetwork.NetworkCommunication.flask_server import FlaskServer
from ALBATROSSProtocol.ALBATROSS import ALBATROSS


BYZANTINE = 0
ABSOLUTE_MAJORITY = 1

# Class that redirects output to both file and terminal
class Logger:
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.log = open(filename, "w")

    def write(self, message):
        self.terminal.write(message)  # Print to terminal
        self.log.write(message)       # Save to file

    def flush(self):
        pass


def signal_handler():
    print("Shutting down the server...")
    sys.exit(0)

# Terminal commands
def manage_terminal_input():
    # Capture Ctrl+C signal using signal_handler
    signal.signal(signal.SIGINT, signal_handler)

    # Capture the number of participants from terminal input
    parser = argparse.ArgumentParser(description="Process two input numbers.")
    parser.add_argument('--n', type=int, default=24, help='Number of participants.')
    args = parser.parse_args()
    if args.n < 10:
        args.n = 24
    print(f"Number of participants: {args.n}")
    return args.n

# Create the network
def create_network(num_participants, num_malicious_participants):
    network = Network(num_participants)
    network.create_nodes(num_malicious_participants)
    network.assign_neighbors()
    network.pk_to_ledger()
    # network.visualize_network()
    return network
 
# Start the Flask server
def start_flask_server(network):
    flask_server = FlaskServer(network)
    def run_server():
        flask_server.run()

    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()
    time.sleep(2)  # Give time for the server to start
    return server_thread

def test(participants, num_malicious_participants, system):
    """
    system: BYZANTINE (2/3) o ABSOLUTE_MAJORITY (50%+1)
    """
    #num_participants = manage_terminal_input() # solo si uso entrada por teclado para arrancarlo

    # Byzantine Fault Tolerance: esto significa que necesita n>=3t+1, donde n es nodos y t nodos maliciosos, luego, el m´niimo de nodos para ejecutar albatros es 4, ¿no?
    #if participants < 3*num_malicious_participants+1:
    if system == BYZANTINE:
        if participants // 3 < num_malicious_participants:
            #20
            #20//3=6
            print("Error: No hay suficientes nodos honestos para reconstruir el secreto por método bizantino")
            print(f"part: {participants}, bizantino, honest_needed_min {participants - participants // 3} maliciosos {num_malicious_participants}, resultado {participants / 2 < participants // 3}")
            return 0, 0, 0, participants, num_malicious_participants, 0
    elif system == ABSOLUTE_MAJORITY:
        if participants/2 <= num_malicious_participants:
            print("Error: No hay suficientes nodos honestos para reconstruir el secreto por mayoría absoluta")
            print(f"part: {participants}, ABSOLUTE_MAJORITY, honest_needed_min {int(participants / 2 + 1)} maliciosos {num_malicious_participants} resultado {participants / 2 < num_malicious_participants + 1}")
            return 0, 0, 0, participants, num_malicious_participants, 0
    elif system != ABSOLUTE_MAJORITY and system != BYZANTINE:
        print("Error: No se especificó el sistema de reconstrucción de secretos: falta el número de nodos honestos mínimos")
        exit(0)

    exit(0)
    network = create_network(participants, num_malicious_participants)

    start_flask_server(network)
    start_time = time.time()
    protocol = ALBATROSS(network, participants)
    commit_time = protocol.execute_commit_phase()
    reveal_time = protocol.execute_reveal_phase()
    output_time = protocol.handle_output_phase()
    end_time = time.time()
    execution_time = end_time - start_time

    return commit_time, execution_time, output_time, participants, num_malicious_participants, reveal_time


def test_repetitions(participants, num_malicious_participants, repetitions):
    all_times = []
    for r in repetitions:
        times = test(participants, num_malicious_participants)
        all_times [r] = times
        print(f"test {r} with {participants} participants and {num_malicious_participants} malicious participants")
        print_time(times[0], times[1], times[2], times[3], times[4])

    print(f"Tiempo menor: {min_time(all_times)} seconds")
    print(f"Tiempo medio: {average_time(all_times)} seconds")
    print(f"Tiempo mayor: {max_time(all_times)} seconds")


# hacer prueba con una array fácil que meta yo harcodeado, y comprobar el infinito
def min_time(all_times):
    min_times = []
    pos = 0

    for t1 in all_times:
        aux = float('inf')
        for t2 in t1:
            if t2 < aux:
                aux = t2
                min_times[pos] = aux
        min_times[pos] = aux
        pos += 1
    return min_times


# hacer prueba con una array fácil que meta yo harcodeado
def average_time(all_times):
    average_times = []
    pos = 0

    for t1 in all_times:
        aux = 0
        len = 0
        for t2 in t1:
            aux += t2
            len += 1
        average_times[pos] = aux/len
        pos += 1
    return average_times


# hacer prueba con una array fácil que meta yo harcodeado
def max_time(all_times):
    max_times = []
    pos = 0

    for t1 in all_times:
        aux = 0
        sys.stdout = Logger(f"log{aux}.txt")
        for t2 in t1:
            if t2 > aux:
                aux = t2
        max_times[pos] = aux
        pos += 1
    return max_times


def print_time(commit_time: float, execution_time: float, output_time: float, participants, num_malicious_participants, reveal_time: float):
    print("########################### EXECUTION TIMES ###########################")
    print(f"N: {participants} participants")
    print(f"N: {num_malicious_participants} malicious participants")
    print(f"Total: {execution_time} seconds")
    print(f"Commit: {commit_time} seconds")
    print(f"Reveal: {reveal_time} seconds")
    print(f"Output: {output_time} seconds")

##duda: albatros usa Byzantine Fault Tolerance, esto significa que necesita n>=3t+1, donde n es nodos y t nodos maliciosos, luego, el mínimo de nodos para ejecutar albatros es 4, ¿no? o si l ohago con 6 nodos, basta con que haya 4 buenos y 2 malos como mínimo, pq 3 y 3 entiendfo que no sirve
###Octavian metía un 0,15 de probabilidad de no honestos, es decir, estadísticamente había 0 o 1 normalente, o 2, por eso a veces cascaba al final, en la recosntrucción, pero n oexplicaba bien pq, decía que n ohabía suficiente matriz (ValueError: Sample larger than population or is negative)
##mejorar que solo levante elservidor una vez y dp haga la spruebas con todo sin relevantar todo de nuevo
## sacar umbral t que es // 3 a una variable global constant,e o definible, preguntar aver si tiene sentido
##hacer: localziar la creación de la clase nodo en Albatross para pdoer seleccionar otra diferente que cumpla lo mismo
##hacer: mirar pq no usa toda la CPU: optimizarlo con asyncio o multiprocessing para mejorar el uso de CPU
##hacer: https://www.keylength.com/ (Domingo ha sugerido que se use https://www.keylength.com para discutir las implicaciones de elección de clave para el problema del logaritmo discreto en compatación con curvas elípticas (como el Elliptic Diffie Hellman)
# hacer: # prueba 6-4:  secs / / 51,4 // sin mi if de comprobación, el programa traga (corregir), el problema, creo, es que se queda con la parte entera de la divisiñon,luego, 6/4=1, y debería ser co nel redondeo hacia arriba por si hay 2 maliciosos, pq en verdad el umbral que marc ahardcodeado es siempre //3, luego 6//3 = 2
# Main function
if __name__ == '__main__':
    # Redirect standard output and errors to both log.txt and terminal
    sys.stdout = Logger("log.txt")
    sys.stderr = sys.stdout

    #test_time = test(3)
    #print_time(test_time[0], test_time[1], test_time[2], test_time[3], test_time[4])
    ## error: ValueError: Sample larger than population or is negative

    #print(f"3//4 {3 // 4}") # 0
    #print(f"3//3 {3 // 3}") # 1
    #print(f"3//2 {3 // 2}") # 1
    #print(f"3//1 {3 // 1}") # 3
    #print(f"3//0 {3 // 0}") # error

    test_time = test(6, 2, BYZANTINE)
    print_time(test_time[0], test_time[1], test_time[2], test_time[3], test_time[4], test_time[5])
    # 6-0: 32 secs
    # 6-1: 32 secs
    #Deberían fallar y decir "No hay suficientes nodos honestos para reconstruir el secreto":
    # 6-2: 33 secs / 50 /51,85 // sin mi if de comprobación, el programa traga (corregir), nota al inicio de este método
    # 6-3:  secs / / 51,6 // sin mi if de comprobación, el programa traga (corregir), nota al inicio de este método
    # 6-4:  secs / / 51,4 // sin mi if de comprobación, el programa traga (corregir), nota al inicio de este método
    # 6-5:  secs / / ValueError: Sample larger than population or is negative
    # 6-6:  secs / / ValueError: Sample larger than population or is negative

    #test_time = test(7)
    #print_time(test_time[0], test_time[1], test_time[2], test_time[3], test_time[4])
    # 58 secs

    #test_time = test(9)
    #print_time(test_time[0], test_time[1], test_time[2], test_time[3], test_time[4])
    # 72 secs

    #test_time = test(12)
    #print_time(test_time[0], test_time[1], test_time[2], test_time[3], test_time[4])

    #test_time = test(18)
    #print_time(test_time[0], test_time[1], test_time[2], test_time[3], test_time[4])

    # test_time = test(24, 9)
    # print_time(test_time[0], test_time[1], test_time[2], test_time[3], test_time[4], test_time[5])
    # 24-0: 243 secs
    # 24-8: 338 secs
    # 24-10: no permite por mi if, o peta con ValueError("Sample larger than population or is negative")
    # 24-11:  no permite por mi if, o peta con ValueError("Sample larger than population or is negative")

    #test_time = test(33)
    #print_time(test_time[0], test_time[1], test_time[2], test_time[3], test_time[4])

    #test_time = test(39)
    #print_time(test_time[0], test_time[1], test_time[2], test_time[3], test_time[4])

    #test_time = test(51)
    #print_time(test_time[0], test_time[1], test_time[2], test_time[3], test_time[4])
    #python me consume 15% cpu y 118 mb de ram y pycharm 14% y 1800 y tarda mucho en hacerse, más que lo de Octavia
    # si hago más de un test a la vez peta, creo que pq no cierra los nodos o no los reinicia o algo
    # el de 51 se quedó en "Some reveals failed. Proceeding with alternative action." Clase Albatross linea 137

    exit(0)
    # Keep the main thread active
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Server stopped.")
