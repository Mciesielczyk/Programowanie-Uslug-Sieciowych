import socket

# 1. Tworzymy gniazdo UDP
# AF_INET = IPv4
server_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# 2. Rezerwujemy port (ten sam mechanizm co w TCP)
server_udp.bind(('127.0.0.1', 22222))

print("Serwer UDP (3.0) czeka na paczki na porcie 22222...")

while True:
    # 3. Odbieramy dane
    # recvfrom zwraca: (dane, (adres_nadawcy, port_nadawcy))
    data, addr = server_udp.recvfrom(1024)
    
    print(f"Odebrano wiadomość: '{data.decode()}' od {addr}")
    
    # 4. Odpowiadamy (musimy podać adres, bo nie ma stałego połączenia!)
    server_udp.sendto("Serwer UDP potwierdza odbiór!".encode(), addr)

server_udp.close()