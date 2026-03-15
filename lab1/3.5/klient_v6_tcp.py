import socket

client_v6 = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)

# Łączymy się z adresem IPv6
client_v6.connect(('::1', 12345))

client_v6.send("Cześć serwerze, tu klient IPv6!".encode())
response = client_v6.recv(1024)
print(f"Odpowiedź: {response.decode()}")

client_v6.close()