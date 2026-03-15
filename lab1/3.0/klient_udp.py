import socket

# 1. Tworzymy gniazdo UDP
client_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

server_addr = ('127.0.0.1', 22222)
message = "Hej UDP, dotarłeś?"

# 2. Wysyłamy dane (używamy sendto, bo musimy celować w konkretny adres)
client_udp.sendto(message.encode(), server_addr)

# 3. Czekamy na odpowiedź
data, server = client_udp.recvfrom(1024)
print(f"Serwer odpowiedział: {data.decode()}")

client_udp.close()