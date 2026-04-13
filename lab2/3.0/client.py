import socket
import ssl

HOST = '127.0.0.1'
PORT = 8000


context = ssl.create_default_context()
context.load_verify_locations("server.crt")

with socket.create_connection((HOST, PORT)) as sock:
    with context.wrap_socket(sock, server_hostname="localhost") as ssock:
        print(f"[*] Połączono z serwerem przez {ssock.version()}")
        ssock.sendall(b"Czesc serwerze, tu bezpieczny klient!")
        response = ssock.recv(1024)
        print(f"[*] Odpowiedź serwera: {response.decode()}")