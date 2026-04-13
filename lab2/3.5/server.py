import socket
import ssl

HOST = '127.0.0.1'
PORT = 8000

context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
context.load_cert_chain(certfile="server.crt", keyfile="server.key")

bindsocket = socket.socket()
bindsocket.bind((HOST, PORT))
bindsocket.listen(5)

print(f"[*] Serwer TLS uruchomiony na {HOST}:{PORT}")

while True:
    newsock, fromaddr = bindsocket.accept()
    try:
   
        connstream = context.wrap_socket(newsock, server_side=True)
        try:
            data = connstream.recv(1024)
            print(f"[*] Otrzymano: {data.decode()}")
            connstream.sendall(b"Wiadomosc odebrana bezpiecznie!")
        finally:
            connstream.shutdown(socket.SHUT_RDWR)
            connstream.close()
    except ssl.SSLError as e:
        print(f"[!] Błąd SSL z {fromaddr}: {e}")
    except Exception as e:
        print(f"[!] Inny błąd: {e}")