import socket
import ssl

HOST = '127.0.0.1'
PORT = 8000

context = ssl.create_default_context()
# Tu wczytujemy COKOLWIEK innego niż poprawne myCA.pem
# Może to być pusty plik albo certyfikat innego urzędu
try:
    context.load_verify_locations("server.crt") # Próbujemy ufać staremu plikowi zamiast CA
except:
    pass 

print("[!] TEST: Klient próbuje połączyć się z serwerem CA, ale nie zna tego CA...")

try:
    with socket.create_connection((HOST, PORT)) as sock:
        with context.wrap_socket(sock, server_hostname="localhost") as ssock:
            print("[-] BŁĄD: Połączono! (To nie powinno się stać)")
except ssl.SSLCertVerificationError:
    print("[+] SUKCES: Klient odrzucił serwer, bo certyfikat serwera nie został podpisany przez znane mu CA.")
except Exception as e:
    print(f"[*] Inny błąd: {e}")