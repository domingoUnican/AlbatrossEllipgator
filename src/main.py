import argparse
import sys
import time
import signal

import config

from DistributedNetwork.NetworkManagement.network import Network
from DistributedNetwork.NetworkCommunication.flask_server import FlaskServer
from ALBATROSSProtocol.ALBATROSS import ALBATROSS

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
def create_network(num_participants, num_malicious_participants, t, EC=True):
    network = Network(num_participants, EC)
    network.create_nodes(num_malicious_participants, t)
    network.assign_neighbors()
    network.pk_to_ledger()
    # network.visualize_network()
    return network
 
# Start the Flask server
def start_flask_server(network):
    # FlaskServer ahora hereda de Thread, no de process
    server_thread = FlaskServer(network)
    server_thread.daemon = True
    server_thread.start()
    time.sleep(2)  # Tiempo a que levante el puerto
    return server_thread

def test(participants, num_malicious_participants, system, EC, mode):
    """
        system: BYZANTINE (2/3) o ABSOLUTE_MAJORITY (50%+1)
    """
    #num_participants = manage_terminal_input() # solo si uso entrada por teclado para arrancarlo
    t = 0 # # Nodos maliciosos/traidores tolerados
    # Byzantine Fault Tolerance: esto significa que necesita n>=3t+1, donde n es nodos y t nodos maliciosos, luego, el m´niimo de nodos para ejecutar albatros es 4, ¿no?
    if system == config.BYZANTINE:
        t = (participants - 1) // 3
        if t < num_malicious_participants:
            #20
            #20//3=6
            print("Error: No hay suficientes nodos honestos para reconstruir el secreto por método bizantino")
            print(f"part: {participants}, bizantino, honest_needed_min {participants - participants // 3} maliciosos {num_malicious_participants}, resultado {participants / 2 < participants // 3}")
            exit(0)
    elif system == config.ABSOLUTE_MAJORITY:
        t = (participants - 1) // 2
        if t < num_malicious_participants:
            print("Error: No hay suficientes nodos honestos para reconstruir el secreto por mayoría absoluta")
            print(f"part: {participants}, ABSOLUTE_MAJORITY, honest_needed_min {int(participants / 2 + 1)} maliciosos {num_malicious_participants} resultado {participants / 2 < num_malicious_participants + 1}")
            exit(0)
    elif system != config.ABSOLUTE_MAJORITY and system != config.BYZANTINE:
        print("Error: No se especificó el sistema de reconstrucción de secretos: falta elegir el número de nodos honestos mínimos")
        exit(0)

    network = create_network(participants, num_malicious_participants, t, EC=EC)
    server_thread = start_flask_server(network)

    start_time = time.perf_counter()
    protocol = ALBATROSS(network, participants, system, mode)
    commit_time = protocol.execute_commit_phase()
    reveal_time = protocol.execute_reveal_phase()
    output_time = protocol.handle_output_phase()
    end_time = time.perf_counter()

    execution_time = end_time - start_time

    # Apagamos el hilo de Flask limpiamente
    server_thread.shutdown()
    server_thread.join()

    return commit_time, execution_time, output_time, participants, num_malicious_participants, reveal_time


def print_time(commit_time: float, execution_time: float, output_time: float, participants, num_malicious_participants, reveal_time: float):
    print("########################### EXECUTION TIMES ###########################")
    print(f"N: {participants} participants")
    print(f"N: {num_malicious_participants} malicious participants")
    print(f"Total: {execution_time:.4f} seconds")
    print(f"Commit: {commit_time:.4f} seconds")
    print(f"Reveal: {reveal_time:.4f} seconds")
    print(f"Output: {output_time:.4f} seconds")
    print("#######################################################################")
    print("\n"*2)

def test_classic(participants, malicious, system):
    test_time = test(participants, malicious, system, EC=False, mode=config.CLASSIC_MODE)
    print_time(test_time[0], test_time[1], test_time[2], test_time[3], test_time[4], test_time[5])
    return test_time


def test_ec_simple(participants, malicious, system):
    test_time = test(participants, malicious, system, EC=True, mode=config.EC_MODE)
    print_time(test_time[0], test_time[1], test_time[2], test_time[3], test_time[4], test_time[5])
    return test_time


def test_elligator(participants, malicious, system):
    test_time = test(participants, malicious, system, EC=True, mode=config.ELLIGATOR_MODE)
    print_time(test_time[0], test_time[1], test_time[2], test_time[3], test_time[4], test_time[5])
    return test_time

def console_mode():
    # Keep the main thread active
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Server stopped.")

def print_final_table(summary_results):
    print("\n\n" + "#" * 80)
    print("### RESUMEN FINAL DE TIEMPOS DE OUTPUT (Segundos) ###")
    print("#" * 80)

    # Cabecera de la tabla
    header = f"| {'Nodos (N)':<10} | {'Maliciosos (t)':<15} | {'Clásica':<12} | {'EC Simple':<12} | {'Elligator':<12} |"
    print("-" * len(header))
    print(header)
    print("-" * len(header))

    for (N, t) in summary_results:
        res = summary_results[(N, t)]

        # Formateamos a 4 decimales si hay dato, si no ponemos un guion "-"
        t_class = f"{res.get(config.CLASSIC_MODE, 0):.4f}" if config.CLASSIC_MODE in res else "-"
        t_ec = f"{res.get(config.EC_MODE, 0):.4f}" if config.EC_MODE in res else "-"
        t_elli = f"{res.get(config.ELLIGATOR_MODE, 0):.4f}" if config.ELLIGATOR_MODE in res else "-"

        print(f"| {N:<10} | {t:<15} | {t_class:<12} | {t_ec:<12} | {t_elli:<12} |")

    print("-" * len(header))

# Main function
if __name__ == '__main__':
    # Redirect standard output and errors to both log.txt and terminal
    sys.stdout = Logger("log.txt")
    sys.stderr = sys.stdout

    # Usamos argparse para elegir los tests al arrancar
    parser = argparse.ArgumentParser(description="Ejecutor de pruebas ALBATROSS")

    # El parámetro nargs='+' permite escribir varios argumentos: --tests ec classic
    parser.add_argument('--tests', nargs='+', choices=[config.CLASSIC_MODE, config.EC_MODE, config.ELLIGATOR_MODE, 'all'],
                        default=config.DEFAULT_TESTS_TO_RUN,
                        help='Elige qué pruebas ejecutar separadas por espacio (ej: --tests ec classic) o "all" para todas')

    args, unknown = parser.parse_known_args()

    # Si el usuario escribe 'all', metemos las tres en la lista
    test_to_do = args.tests
    if 'all' in test_to_do:
        test_to_do = [config.CLASSIC_MODE, config.EC_MODE, config.ELLIGATOR_MODE]

    # Diccionario para guardar los resultados y pintar la tabla luego
    # Formato: {(participantes, maliciosos): {'classic': time, 'ec': time, 'elligator': time}}
    summary_results = {(p, m): {} for p, m, _ in config.ACTIVE_TEST_CASES}

    if config.CLASSIC_MODE in test_to_do:
        print("\n" * 4)
        print("########################################################################################")
        print("########################### Ejecutando Clásica sin EC... ###############################")
        print("########################################################################################")
        for participants, malicious, system in config.TEST_CASES:
            result = test_classic(participants, malicious, system)
            if result:
                summary_results[(participants, malicious)][config.CLASSIC_MODE] = result[2]  # output_time

    if config.EC_MODE in test_to_do:
        print("\n" * 4)
        print("########################################################################################")
        print("########################### Ejecutando EC Simple... ####################################")
        print("########################################################################################")
        for participants, malicious, system in config.TEST_CASES:
            result = test_ec_simple(participants, malicious, system)
            if result:
                summary_results[(participants, malicious)][config.EC_MODE] = result[2]  # output_time

    if config.ELLIGATOR_MODE in test_to_do:
        print("\n" * 4)
        print("########################################################################################")
        print("########################### Ejecutando Elligator... ###################################")
        print("########################################################################################")
        for participants, malicious, system in config.TEST_CASES:
            result = test_elligator(participants, malicious, system)
            if result:
                summary_results[(participants, malicious)][config.ELLIGATOR_MODE] = result[2]  # output_time

    print_final_table(summary_results)

    print("\n[+] Todas las pruebas finalizadas.")

    exit(0)

