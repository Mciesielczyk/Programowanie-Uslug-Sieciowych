import socket
import ssl

HOST = '127.0.0.1'
PORT = 8000

context = ssl.create_default_context()
context.load_verify_locations("myCA.pem")

try:
    with socket.create_connection((HOST, PORT)) as sock:
        with context.wrap_socket(sock, server_hostname="localhost") as ssock:
            print(f"[*] Połączono pomyślnie używając TLS!")
            print(f"[*] Certyfikat serwera zweryfikowany przez nasze CA.")
            ssock.sendall(b"Czesc, ufam Twojemu urzedowi CA!")
            print(f"[*] Serwer odpowiedzial: {ssock.recv(1024).decode()}")
except Exception as e:
    print(f"[!] Blad: {e}")