class SecretManagement:
    """Herramienta para escribir y leer secretos simulando el I/O de Albatross"""

    def save_text_as_matrix(texto: str, nombre_archivo: str = "mi_secreto.txt"):
        """Convierte tu texto a número y lo guarda con el formato Numpy de Albatross"""
        # Texto a bytes -> Bytes a Número entero gigante
        numero_gigante = int.from_bytes(texto.encode('utf-8'), 'big')

        # Simulamos el formato en el que lo guarda Numpy "[[ numero ]]"
        formato_numpy = f"[[{numero_gigante}]]"

        with open(nombre_archivo, 'w') as f:
            f.write(formato_numpy)
        print(f"[*] Secreto '{texto}' guardado en {nombre_archivo}")

    def read_matrix_as_text(nombre_archivo: str = "mi_secreto.txt") -> str:
        """Lee el archivo sucio de Numpy y extrae el texto original"""
        try:
            with open(nombre_archivo, 'r') as f:
                contenido = f.read()

            # Limpiamos los corchetes y saltos de línea de Numpy
            numero_str = contenido.replace('[', '').replace(']', '').replace('\n', '').strip()

            if not numero_str:
                return "Error: El archivo está vacío"

            # Convertimos el string numérico al int gigante
            numero_gigante = int(numero_str)

            # Número gigante a bytes -> Bytes a texto
            num_bytes = (numero_gigante.bit_length() + 7) // 8
            texto_recuperado = numero_gigante.to_bytes(num_bytes, 'big').decode('utf-8')

            return texto_recuperado

        except FileNotFoundError:
            return f"Error: No se encontró el archivo {nombre_archivo}"
        except UnicodeDecodeError:
            return "Error: El número guardado no es texto válido (probablemente es ruido matemático o la basura antigua)."
        except ValueError:
            return f"Error: No se pudo convertir '{numero_str}' a número."

# Main function
if __name__ == '__main__':
    SecretManagement.save_text_as_matrix("¡Secreto de prueba", "prueba_io.txt")
    print(SecretManagement.read_matrix_as_text("prueba_io.txt"))

    exit(0)