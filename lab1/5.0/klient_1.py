import socket

# 1. Tworzymy gniazdo
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# 2. Łączymy się z serwerem
client_socket.connect(('172.30.46.58', 12345))
# 3. Wysyłamy dane
client_socket.send("Cześć serwerze!".encode())

# 4. Odbieramy odpowiedź
response = client_socket.recv(1024)
print(f"Serwer odpowiedział: {response.decode()}")

# 5. Zamykamy
client_socket.close()