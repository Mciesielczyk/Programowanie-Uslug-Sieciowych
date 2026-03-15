import socket

# ZMIANA 1: AF_INET6 zamiast AF_INET
server_v6 = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)

# ZMIANA 2: Adres '::1' to lokalny host w IPv6
# Port zostawiamy bez zmian (np. 12345)
server_v6.bind(('::1', 12345))

server_v6.listen(1)
print("Serwer IPv6 TCP nasłuchuje na [::1]:12345...")

conn, addr = server_v6.accept()
print(f"Połączono z adresem IPv6: {addr}")

data = conn.recv(1024)
print(f"Odebrano: {data.decode()}")

conn.send("Potwierdzam odbiór przez IPv6!".encode())
conn.close()