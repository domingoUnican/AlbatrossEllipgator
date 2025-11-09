# Proyecto ALBATROSS

Este proyecto es una **simulación del protocolo ALBATROSS** en una red distribuida. Está diseñado para probar la implementación del protocolo en un entorno controlado y permite evaluar cómo funciona la generación de aleatoriedad distribuida entre un grupo de participantes.

## Descripción

ALBATROSS es un protocolo criptográfico que facilita la generación de aleatoriedad de manera distribuida entre varios participantes. Este proyecto simula cómo distintos nodos (participantes) en una red pueden ejecutar el protocolo de forma autónoma y segura, asegurando que todos los nodos puedan generar aleatoriedad sin depender de una autoridad central.

La simulación se realiza mediante un conjunto de nodos que interactúan entre sí utilizando una red distribuida. Cada nodo ejecuta una parte del protocolo ALBATROSS de forma independiente y se comunica con otros nodos a través de un **registro público** (ledger) para sincronizar su ejecución.

## Requisitos

- Python 3.8 o superior
- Dependencias listadas en `requirements.txt`

Puedes instalar las dependencias necesarias ejecutando:

```bash
pip install -r requirements.txt
```

Puedes instalar las dependencias necesarias ejecutando:

```bash
python .\src\main.py --n [número de participantes]
--n           Establece el número de participantes n en el argumento, sin esta opción n = 24
```
