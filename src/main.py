import argparse
import sys
import threading
import time
import signal

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
    network = Network(num_participants,True)
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
    return flask_server, server_thread


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
            exit(0)
    elif system == ABSOLUTE_MAJORITY:
        if participants/2 <= num_malicious_participants:
            print("Error: No hay suficientes nodos honestos para reconstruir el secreto por mayoría absoluta")
            print(f"part: {participants}, ABSOLUTE_MAJORITY, honest_needed_min {int(participants / 2 + 1)} maliciosos {num_malicious_participants} resultado {participants / 2 < num_malicious_participants + 1}")
            exit(0)
    elif system != ABSOLUTE_MAJORITY and system != BYZANTINE:
        print("Error: No se especificó el sistema de reconstrucción de secretos: falta elegir el número de nodos honestos mínimos")
        exit(0)

    network = create_network(participants, num_malicious_participants)
    server, threads = start_flask_server(network)
    #server.change_network(network)

    start_time = time.time()
    protocol = ALBATROSS(network, participants, system)
    commit_time = protocol.execute_commit_phase()
    reveal_time = protocol.execute_reveal_phase()
    output_time = protocol.handle_output_phase()
    end_time = time.time()
    execution_time = end_time - start_time

    #network.clear_nodes()
    #network.clear()
    #protocol.clear()
    #shutdown_and_reset(server, network, threads) # si lo descomento, se cuelga y no continua el proceso y no muestra los tiempos

    return commit_time, execution_time, output_time, participants, num_malicious_participants, reveal_time


def print_time(commit_time: float, execution_time: float, output_time: float, participants, num_malicious_participants, reveal_time: float):
    print("########################### EXECUTION TIMES ###########################")
    print(f"N: {participants} participants")
    print(f"N: {num_malicious_participants} malicious participants")
    print(f"Total: {execution_time} seconds")
    print(f"Commit: {commit_time} seconds")
    print(f"Reveal: {reveal_time} seconds")
    print(f"Output: {output_time} seconds")


def test_ec_simple():
    test_time = test(40, 13, BYZANTINE)
    print_time(test_time[0], test_time[1], test_time[2], test_time[3], test_time[4], test_time[5])

    """
    test_time = test(5, 0, BYZANTINE)
    print_time(test_time[0], test_time[1], test_time[2], test_time[3], test_time[4], test_time[5])
    
    test_time = test(5, 1, BYZANTINE)
    print_time(test_time[0], test_time[1], test_time[2], test_time[3], test_time[4], test_time[5])

    test_time = test(10, 0, BYZANTINE)
    print_time(test_time[0], test_time[1], test_time[2], test_time[3], test_time[4], test_time[5])

    test_time = test(10, 3, BYZANTINE)
    print_time(test_time[0], test_time[1], test_time[2], test_time[3], test_time[4], test_time[5])

    test_time = test(20, 0, BYZANTINE)
    print_time(test_time[0], test_time[1], test_time[2], test_time[3], test_time[4], test_time[5])

    test_time = test(20, 6, BYZANTINE)
    print_time(test_time[0], test_time[1], test_time[2], test_time[3], test_time[4], test_time[5])

    test_time = test(30, 0, BYZANTINE)
    print_time(test_time[0], test_time[1], test_time[2], test_time[3], test_time[4], test_time[5])

    test_time = test(30, 10, BYZANTINE)
    print_time(test_time[0], test_time[1], test_time[2], test_time[3], test_time[4], test_time[5])

    test_time = test(40, 0, BYZANTINE)
    print_time(test_time[0], test_time[1], test_time[2], test_time[3], test_time[4], test_time[5])

    test_time = test(40, 13, BYZANTINE)
    print_time(test_time[0], test_time[1], test_time[2], test_time[3], test_time[4], test_time[5])
    """

def console_mode():
    # Keep the main thread active
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Server stopped.")

# Main function
if __name__ == '__main__':
    # Redirect standard output and errors to both log.txt and terminal
    sys.stdout = Logger("log.txt")
    sys.stderr = sys.stdout

    test_ec_simple()

    exit(0)

