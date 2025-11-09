from flask import Flask
from ..NetworkCommunication.controller import NodeController

class FlaskServer:
    def __init__(self, network):
        self.__app = Flask(__name__)  # Create the Flask application
        self.__node_controller = NodeController(network)  # Instantiate the node controller with the network
        self.__app.register_blueprint(self.__node_controller.get_blueprint())

    def run(self, host="0.0.0.0", port=5000, debug=False):
        self.__app.run(host=host, port=port, debug=debug)
