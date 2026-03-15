import socket
import struct
import os

# --- FUNKCJE POMOCNICZE ---

def checksum(msg):
    """Oblicza sumę kontrolną (wymagane w nagłówkach sieciowych)"""
    s = 0
    for i in range(0, len(msg), 2):
        w = (msg[i] << 8) + (msg[i+1])
        s = s + w
    s = (s >> 16) + (s & 0xffff)
    s = ~s & 0xffff
    return s

# --- IMPLEMENTACJA KLIENTA (NADAWCA) ---

def run_client():
    dest_ip = "127.0.0.1"
    print("\nWybierz protokół do wysłania:")
    print("1. ICMP (Ping)")
    print("2. UDP (User Datagram)")
    choice = input("Wybór: ")

    if choice == '1':
        # RAW ICMP
        s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
        # Nagłówek ICMP: Typ(8), Kod(0), Checksum(0), ID(1), Seq(1)
        header = struct.pack('!BBHHH', 8, 0, 0, 1, 1)
        data = b"Hello ICMP Raw"
        my_check = checksum(header + data)
        header = struct.pack('!BBHHH', 8, 0, my_check, 1, 1)
        packet = header + data
        s.sendto(packet, (dest_ip, 0))
        print("Wysłano surowy pakiet ICMP!")

    elif choice == '2':
        # RAW UDP (Wymaga budowania nagłówka UDP ręcznie)
        s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_UDP)
        sport = 12345
        dport = 54321
        length = 8 + len(b"Hello UDP Raw")
        # Nagłówek UDP: PortS(2b), PortD(2b), Len(2b), Checksum(2b)
        header = struct.pack('!HHHH', sport, dport, length, 0)
        packet = header + b"Hello UDP Raw"
        s.sendto(packet, (dest_ip, dport))
        print(f"Wysłano surowy pakiet UDP na port {dport}!")

# --- IMPLEMENTACJA SERWERA (ODBIORCA) ---

def run_server():
    print("\nJakiego ruchu chcesz nasłuchiwać?")
    print("1. ICMP")
    print("2. UDP")
    choice = input("Wybór: ")

    proto = socket.IPPROTO_ICMP if choice == '1' else socket.IPPROTO_UDP
    s = socket.socket(socket.AF_INET, socket.SOCK_RAW, proto)
    print("Serwer RAW uruchomiony... Czekam na dane.")

    while True:
        raw_packet, addr = s.recvfrom(65535)
        # Nagłówek IP ma zawsze 20 bajtów
        ip_header = raw_packet[:20]
        # Rozpakowujemy adresy IP z nagłówka
        iph = struct.unpack('!BBHHHBBH4s4s', ip_header)
        src_ip = socket.inet_ntoa(iph[8])
        
        # Dane zaczynają się po nagłówku IP (20b) i nagłówku protokołu (np. 8b)
        offset = 20 + (8 if choice == '2' else 8) 
        data = raw_packet[offset:]
        
        print(f"\n[ZŁAPANO PAKIET] Od: {src_ip}")
        print(f"Surowe dane: {data.decode(errors='ignore')}")

# --- MENU GŁÓWNE ---

if __name__ == "__main__":
    print("--- STARTER PACK RAW SOCKETS ---")
    mode = input("Wybierz tryb: (S)erwer / (K)lient: ").upper()
    if mode == 'S':
        run_server()
    else:
        run_client()