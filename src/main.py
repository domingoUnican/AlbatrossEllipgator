import argparse
import sys
import threading
import time
import signal

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
def create_network(num_participants):
    network = Network(num_participants,True)
    network.create_nodes()
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

# Main function
if __name__ == '__main__':
    # Redirect standard output and errors to both log.txt and terminal
    sys.stdout = Logger("log.txt")
    sys.stderr = sys.stdout

    #num_participants = manage_terminal_input()
    num_participants = 10
    network = create_network(num_participants)

    start_flask_server(network)

    start_time = time.time()
    protocol = ALBATROSS(network, num_participants)
    commit_time = protocol.execute_commit_phase() 
    reveal_time = protocol.execute_reveal_phase()
    output_time = protocol.handle_output_phase()
    end_time = time.time()
    execution_time = end_time - start_time

    print("########################### EXECUTION TIMES ###########################")
    print(f"Total: {execution_time} seconds")
    print(f"Commit: {commit_time} seconds")
    print(f"Reveal: {reveal_time} seconds")
    print(f"Output: {output_time} seconds")
    exit(0)
    # Keep the main thread active
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Server stopped.")
