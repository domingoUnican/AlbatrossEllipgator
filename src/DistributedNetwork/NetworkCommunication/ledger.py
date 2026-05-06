from ALBATROSSProtocol.Proofs.DLEQ import DLEQ

from .base_ledger import BaseLedger


class Ledger(BaseLedger):
    def __init__(self, n, q, p, h, pk=None):
        super().__init__(n, q, h, pk=None)
        self.p = p # Primo grande: es el límite. To-do se hace en módulo/dividir por p.
        self.pk = [0] * n # Lista de las claves públicas de todos los vecinos de la red

    def get_p(self):
        return self.p
