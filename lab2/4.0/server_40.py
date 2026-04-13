import socket
import ssl

HOST = '127.0.0.1'
PORT = 8000

context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
context.load_cert_chain(certfile="server.crt", keyfile="server.key")

context.load_verify_locations("myCA.pem")

context.verify_mode = ssl.CERT_REQUIRED

bindsocket = socket.socket()
bindsocket.bind((HOST, PORT))
bindsocket.listen(5)

print("[*] Serwer mTLS (4.0) czeka na zaufanych klientów...")

while True:
    newsock, fromaddr = bindsocket.accept()
    try:
        with context.wrap_socket(newsock, server_side=True) as ssock:
            print(f"[*] Połączono z klientem: {ssock.getpeercert().get('subject')}")
            data = ssock.recv(1024)
            print(f"[*] Klient przysłał: {data.decode()}")
            ssock.sendall(b"Witaj zaufany kliencie!")
    except ssl.SSLError as e:
        print(f"[!] Odmowa dostępu: Klient nie pokazał ważnego certyfikatu! ({e})")
    except Exception as e:
        print(f"[!] Błąd: {e}")