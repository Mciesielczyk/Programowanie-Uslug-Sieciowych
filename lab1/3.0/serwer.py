import socket

# 1. Tworzymy gniazdo (AF_INET = IPv4, SOCK_STREAM = TCP)
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# 2. Rezerwujemy adres i port ('' oznacza wszystkie dostępne interfejsy)
server_socket.bind(('127.0.0.1', 12345))

# 3. Zaczynamy nasłuchiwać
server_socket.listen(1)
print("Serwer czeka na połączenie...")

# 4. Akceptujemy połączenie od klienta
client_conn, client_addr = server_socket.accept()
print(f"Połączono z: {client_addr}")

# 5. Odbieramy dane
data = client_conn.recv(1024)
print(f"Otrzymano wiadomość: {data.decode()}")

# 6. Wysyłamy odpowiedź i zamykamy
client_conn.send("Wiadomość odebrana!".encode())
client_conn.close()
server_socket.close()