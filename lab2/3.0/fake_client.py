import socket
import ssl

HOST = '127.0.0.1'
PORT = 8000

context = ssl.create_default_context()

print("[!] Próba połączenia bez zaufanego certyfikatu...")

try:
    with socket.create_connection((HOST, PORT)) as sock:
        with context.wrap_socket(sock, server_hostname="localhost") as ssock:
            print("[-] O nie! Połączono (to nie powinno się stać!)")
except ssl.SSLCertVerificationError as e:
    print(f"[+] SUKCES TESTU: Połączenie odrzucone poprawnie!")
    print(f"[+] Powód: {e.reason}")
except Exception as e:
    print(f"[*] Inny błąd: {e}")