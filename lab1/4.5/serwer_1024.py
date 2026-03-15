import socket

HOST = '127.0.0.1'
PORT = 80 
 
server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
 
try:
    server_socket.bind((HOST, PORT))
    print(f"Serwer działa na porcie {PORT} bez uprawnień roota!")
    print("Czekam na wiadomości...\n")
 
    while True:
        data, addr = server_socket.recvfrom(1024)
        print(f"Odebrano od {addr}: {data.decode()}")
        server_socket.sendto(f"Odpowiedź z portu {PORT}!".encode(), addr)
 
except PermissionError:
    print(f"[BŁĄD] Brak uprawnień do portu {PORT}!")
    print("Nadaj uprawnienia komendą:")
    print("  sudo setcap 'cap_net_raw,cap_net_bind_service+ep' $(which python3)")