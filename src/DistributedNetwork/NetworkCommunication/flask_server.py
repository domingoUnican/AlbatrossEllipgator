from flask import Flask, request
from ..NetworkCommunication.controller import NodeController
import os
import threading
import sys


class FlaskServer:
    def __init__(self, network):
        self.__app = Flask(__name__)  # Create the Flask application
        self.__node_controller = NodeController(network)  # Instantiate the node controller with the network
        self.__app.register_blueprint(self.__node_controller.get_blueprint())

        # Define shutdown endpoint
        @self.__app.route('/shutdown', methods=['POST'])
        def shutdown_flask_server():
            """
                # Cierra el servidor Flask sin matar el proceso principal, pero cierra todo el proceso de Python de paso
                shutdown_thread = threading.Thread(target=sys.exit, args=(0,))
                shutdown_thread.start()
                return 'Server shutting down...'
            """
            # os._exit(0)# esto cerraría todo el programa, pero te aseguras que te cierre el servidor
            func = request.environ.get('werkzeug.server.shutdown')
            if func is None:
                raise RuntimeError('Not running with the Werkzeug Server')
            func()
            return 'Server shutting down...'

    def change_network(self, network):
        self.__app = Flask(__name__)
        self.__node_controller = NodeController(network)  # Instantiate the node controller with the network
        self.__app.register_blueprint(self.__node_controller.get_blueprint())

    def run(self, host="0.0.0.0", port=5000, debug=False):
        """
        Por defecto, Flask activa un reloader cuando debug=True. Esto es un segundo proceso para vigilar cambios en el código, para despliegue está bien, para estas pruebas, no, pues lo que hace es reiniciar els ervidor si detecta modificaciones en el código, pero al crear otro proceso, al tratar de matarlo puede que no mate el hilo que necesito, pues el /shutdown solo funciona en el hilo principal, haciendo que el werkzeug.server.shutdown no este disponible en el hilo que se creó. Así, a False, Flask no creará hilso adicionales y correrá un solo proceso y permitirá usar shutdown
        """
        self.__app.run(host=host, port=port, debug=debug, use_reloader=False)


