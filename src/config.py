BYZANTINE = 0
ABSOLUTE_MAJORITY = 1

CLASSIC_MODE = "classic"
EC_MODE = "ec"
ELLIGATOR_MODE = "elligator"

# Array de tuplas para los tests: (participantes, maliciosos, sistema)
TEST_CASES = [
    (4, 0, BYZANTINE),
    (4, 1, BYZANTINE)
]

DEFAULT_TESTS_TO_RUN = ['all']
ACTIVE_TEST_CASES = TEST_CASES

REAL_TEST_CASES = [
    (3, 0, BYZANTINE), # Válida, aunque inútil en el mundo real y para ALBATROSS, solo por tomar tiempos
    (3, 1, BYZANTINE), # No tiene el mínimo de nodos honestos para funcionar
    (4, 0, BYZANTINE),
    (4, 1, BYZANTINE),
    (5, 0, BYZANTINE),
    (5, 1, BYZANTINE),
    (10, 0, BYZANTINE),
    (10, 3, BYZANTINE),
    (20, 0, BYZANTINE),
    (20, 6, BYZANTINE),
    (30, 0, BYZANTINE),
    (30, 10, BYZANTINE),
    (40, 0, BYZANTINE),
    (40, 13, BYZANTINE)
]