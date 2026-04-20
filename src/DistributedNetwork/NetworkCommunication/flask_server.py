import threading
import logging

from flask import Flask
from ..NetworkCommunication.controller import NodeController
from werkzeug.serving import make_server


class FlaskServer(threading.Thread):
    def __init__(self, network, host="0.0.0.0", port=5000):
        threading.Thread.__init__(self)
        self.host = host
        self.port = port
        self.app = Flask(__name__)  # Create the Flask application
        self.node_controller = NodeController(network)  # Instantiate the node controller with the network
        self.app.register_blueprint(self.node_controller.get_blueprint())

        # Silenciamos los logs
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)

        # Instanciamos el servidor de Werkzeug directamente
        self.server = make_server(self.host, self.port, self.app, threaded=True)
        self.ctx = self.app.app_context()
        self.ctx.push()

    def run(self):
        """Se ejecuta al invocar server.start()"""
        self.server.serve_forever()

    def shutdown(self):
        """EApaga el servidor"""
        self.server.shutdown()
        self.ctx.pop()