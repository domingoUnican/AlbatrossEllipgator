from ALBATROSSProtocol.Proofs.LDEI import LDEI

class BaseLedger:
    def __init__(self, n, q, h, pk=None):
        """
        BaseLedger acts as the local state and verifiable data store for a network participant.

            It decouples the consensus state (cryptographic parameters, commitments, and
            secret shares) from the network communication layer (Node). This structure
            ensures that the mathematical engines (e.g., PPVSS) operate exclusively on
            deterministic data structures without side-effects from P2P networking protocols.

            Attributes maintained:
            - Domain parameters (n, t, q, h)
            - Public commitments and Public Keys
            - Private polynomial coefficients (alpha) and randomness (r)
            - Encrypted and verified fragments (shares)
        """

        self.n = n # Número de participantes
        self.q = q # Orden: cantidad de elementos
        self.h = h # Generador: semilla generada para generar todos los elementos del grupo q
        self.t = round(n // 3) # Nodos maliciosos/traidores tolerados
        self.l = n - (2 * self.t) # Secretos empaquetamos a la vez
        self.P = [] # Valores públicos del polinomio que se generaron en la fase de Commit. Se usan para comprobar si alguien miente en las fases de Reveal o Recovery (haciendo las pruebas LDEI o DLEQ)
        self.alpha = [] # Coeficientes del polinomio secreto
        self.r = 0 # Aleatoriedad para evitar que el atacante pueda deducir cuando hay dos operaciones iguales
        self.encrypted_fragments = [] # trozos del secreto encriptados con las PK de los vecinos
        self.revealed_fragments = [0] * n # Secretos recibidos desencriptados con mi PK y que no son falsos tras comprobarlo con ldei
        self.ld = None # List to Dictionary
        self.dl = [0] * n # Dictionary to List

    def new_ld(self):
        self.ld = LDEI()

    def get_n(self):
        return self.n

    def get_t(self):
        return self.t

    def get_l(self):
        return self.l

    def get_q(self):
        return self.q

    def get_h(self):
        return self.h

    def get_pk(self):
        return self.pk

    def get_P(self):
        return self.P

    def get_alpha(self):
        return self.alpha

    def get_encrypted_fragments(self):
        return self.encrypted_fragments

    def get_revealed_fragments(self):
        return self.revealed_fragments

    def get_ld(self):
        return self.ld

    def get_dl(self):
        return self.dl
