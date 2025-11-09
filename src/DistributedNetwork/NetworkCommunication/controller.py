from flask import Blueprint, jsonify, request
from ..NetworkManagement.node import Node
from ..NetworkManagement.network import Network

class NodeController:
    def __init__(self, network):
        self.__controller = Blueprint('controller', __name__)  
        self.__network: Network = network
        self.__nodes: list[Node] = self.__network.get_nodes()
        self.__register_routes()
 
    # Endpoints
    def __register_routes(self):
 
        @self.__controller.route('/node/<int:node_id>/commit')
        def commit(node_id):
            if node_id < len(self.__nodes) and self.__nodes[node_id] is not None:
                result = self.__nodes[node_id].commit()
                return result
            else:
                return f"Node {node_id} not found", 404  
        
        @self.__controller.route('/node/<int:node_id>/reveal')
        def reveal(node_id):
            if node_id < len(self.__nodes) and self.__nodes[node_id] is not None:
                result = self.__nodes[node_id].reveal()
                return result
            else:
                return f"Node {node_id} not found", 404  
            
        @self.__controller.route('/node/<int:node_id>/output')
        def output(node_id):
            if node_id < len(self.__nodes) and self.__nodes[node_id] is not None:
                result = self.__nodes[node_id].output()
                if result == False:
                    return {"status": "failure", "node": node_id}, 500
                else:
                    return {"result": result}, 200  # Returns the result as JSON
            else:
                return f"Node {node_id} not found", 404
        
        @self.__controller.route('/node/<int:node_id>/recovery')
        def recovery(node_id):
            # Get the failed_nodes from URL parameters
            failed_nodes = request.args.get('failed_nodes', '').split(',')
            failed_nodes = [int(node) for node in failed_nodes if node]  # Convert to list of integers
            
            if node_id < len(self.__nodes) and self.__nodes[node_id] is not None:
                result = self.__nodes[node_id].recovery(failed_nodes)  # Pass failed_nodes to recovery function
                if result == False:
                    return {"status": "failure", "node": node_id}, 500
                else:
                    return {"result": result}, 200 
            else:
                return f"Node {node_id} not found", 404
        
        @self.__controller.route('/node/<int:node_id>/reconstruction/<int:reco_id>')
        def reconstruction(node_id, reco_id):
            # Get the reco_parties from query parameters
            reco_parties = request.args.get('reco_parties', '').split(',')
            reco_parties = [int(node) for node in reco_parties if node]  # Convert to list of integers

            if reco_id < len(self.__nodes) and self.__nodes[reco_id] is not None:
                node = self.__nodes[reco_id]
                # Pass node_id and reco_parties to node's reconstruction function
                result = node.reconstruction(node_id, reco_parties)
                
                if result == False:
                    return {"status": "failure", "node": node_id}, 500
                else:
                    return {"result": result}, 200  
            else:
                return f"Node {node_id} not found", 404

        @self.__controller.route('/node/<int:node_id>/decrypt_fragment')
        def decrypt_fragment(node_id):
            i = request.args.get('i')  # Get the 'i' parameter from the URL
            if i is not None:
                i = int(i)  # Convert 'i' to integer
            if node_id < len(self.__nodes) and self.__nodes[node_id] is not None:
                self.__nodes[node_id].decrypt_fragment(i)
                return jsonify({"status": "success", "message": f"Fragment {i} decrypted and uploaded to ledger."})
            else:
                return jsonify({"status": "error", "message": f"Node {node_id} not found"}), 404

        @self.__controller.route('/node/<int:node_id>/verify_lde/<int:ledger_id>')
        def verify_lde(node_id, ledger_id):
            if node_id < len(self.__nodes) and self.__nodes[node_id] is not None:
                node = self.__nodes[node_id]
                if node.verifie_LDEI(ledger_id):
                    return jsonify({"status": "success", "message": "LDEI verified successfully"}), 200
                else:
                    return jsonify({"status": "error", "message": "Incorrect LDEI"}), 400
            return jsonify({"status": "error", "message": "Node not found"}), 404

        @self.__controller.route('/node/<int:node_id>/verify_polynomial/<int:poly_id>')
        def verify_polynomial(node_id, poly_id):
            if node_id < len(self.__nodes) and self.__nodes[node_id] is not None:
                node = self.__nodes[node_id]
                if node.verify_polynomial(poly_id):
                    return jsonify({"status": "success", "message": "Polynomial verified successfully"}), 200
                else:
                    return jsonify({"status": "error", "message": "Incorrect Polynomial"}), 400
            return jsonify({"status": "error", "message": "Node not found"}), 404

        @self.__controller.route('/node/<int:node_id>/verify_dleq/<int:ledger_id>')
        def verify_dleq(node_id, ledger_id):
            failed_nodes = request.args.get('failed_nodes', '').split(',')
            failed_nodes = [int(node) for node in failed_nodes if node]  # Convert to list of integers

            if node_id < len(self.__nodes) and self.__nodes[node_id] is not None:
                node = self.__nodes[node_id]
                if node.verifie_DELQ(ledger_id, failed_nodes):
                    return jsonify({"status": "success", "message": "DLEQ verified successfully"}), 200
                else:
                    return jsonify({"status": "error", "message": "Incorrect DLEQ"}), 400
            return jsonify({"status": "error", "message": "Node not found"}), 404

        @self.__controller.route('/sync_nodes')
        def sync_nodes():
            try:
                self.__network.sync_nodes()  # Call the synchronization method
                return jsonify({"status": "success", "message": "Synchronization completed"}), 200
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500


    def get_blueprint(self):
            return self.__controller
