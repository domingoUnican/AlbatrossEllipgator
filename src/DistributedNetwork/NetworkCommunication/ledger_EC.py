from ALBATROSSProtocol.Proofs.DLEQ import DLEQ

from .base_ledger import BaseLedger

class Ledger_EC(BaseLedger):
    def __init__(self, n, q, h, pk=None):
        super().__init__(n, q, h, pk=None)
        self.pk = [None] * n # Lista de las claves públicas de todos los vecinos de la red

