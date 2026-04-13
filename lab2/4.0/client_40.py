import socket
import ssl

HOST = '127.0.0.1'
PORT = 8000

context = ssl.create_default_context()
context.load_verify_locations("myCA.pem")

context.load_cert_chain(certfile="client.crt", keyfile="client.key")

try:
    with socket.create_connection((HOST, PORT)) as sock:
        with context.wrap_socket(sock, server_hostname="localhost") as ssock:
            print(f"[*] Serwer mnie rozpoznał! Połączono przez {ssock.version()}")
            ssock.sendall(b"Oto moj certyfikat, wpusc mnie!")
            print(f"[*] Odpowiedź: {ssock.recv(1024).decode()}")
except Exception as e:
    print(f"[!] Serwer mnie odrzucił: {e}")