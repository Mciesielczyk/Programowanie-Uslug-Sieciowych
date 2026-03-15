import socket
import struct
import os
import sys

# --- FUNKCJE POMOCNICZE ---

def calculate_checksum(msg):
    """Oblicza sumę kontrolną (RFC 1071)"""
    if len(msg) % 2 != 0:
        msg += b'\x00'
    s = 0
    for i in range(0, len(msg), 2):
        w = (msg[i] << 8) + (msg[i+1])
        s = s + w
    s = (s >> 16) + (s & 0xffff)
    s = ~s & 0xffff
    return s

# --- IMPLEMENTACJA KLIENTA (NADAWCA) ---

def run_client():
    print("\n--- KLIENT RAW ---")
    print("1. IPv4 - ICMP (Ping)")
    print("2. IPv4 - UDP (Port 80)")
    print("3. IPv6 - ICMPv6 (Ping v6)")
    choice = input("Wybór: ")

    if choice == '1':
        # RAW ICMPv4
        dest_ip = "127.0.0.1"
        s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
        header = struct.pack('!BBHHH', 8, 0, 0, 1, 1)
        data = b"Hello ICMPv4 Raw"
        my_check = calculate_checksum(header + data)
        header = struct.pack('!BBHHH', 8, 0, my_check, 1, 1)
        s.sendto(header + data, (dest_ip, 0))
        print(f"Wysłano surowy pakiet ICMPv4 do {dest_ip}")

    elif choice == '2':
        # RAW UDPv4 na port 80 (pokazuje punkt 4.5)
        dest_ip = "127.0.0.1"
        dport = 80
        s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_UDP)
        data = b"Wiadomosc na port 80"
        length = 8 + len(data)
        header = struct.pack('!HHHH', 12345, dport, length, 0)
        s.sendto(header + data, (dest_ip, dport))
        print(f"Wysłano surowy pakiet UDP na port {dport}!")

    elif choice == '3':
        # RAW ICMPv6 (Dla IPv6 system sam liczy sumę kontrolną)
        dest_ip = "::1"
        s = socket.socket(socket.AF_INET6, socket.SOCK_RAW, socket.IPPROTO_ICMPV6)
        header = struct.pack('!BBHHH', 128, 0, 0, 1, 1) # 128 = Echo Request
        data = b"Hello ICMPv6 Raw"
        s.sendto(header + data, (dest_ip, 0))
        print(f"Wysłano surowy pakiet ICMPv6 do {dest_ip}")

# --- IMPLEMENTACJA SERWERA (ODBIORCA) ---

def run_server():
    print("\n--- SERWER RAW / LOW PORT ---")
    print("1. Nasłuchuj ICMP (IPv4)")
    print("2. Nasłuchuj UDP na porcie 80 (IPv4)")
    print("3. Nasłuchuj ICMPv6 (IPv6)")
    choice = input("Wybór: ")

    try:
        if choice == '1':
            s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
            print("Serwer ICMPv4 nasłuchuje...")
        elif choice == '2':
            # Tu pokazujemy punkt 4.5: bindowanie do portu 80
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP
            s.bind(('0.0.0.0', 80))
            print("Serwer UDP nasłuchuje na porcie 80...")
        elif choice == '3':
            s = socket.socket(socket.AF_INET6, socket.SOCK_RAW, socket.IPPROTO_ICMPV6)
            print("Serwer ICMPv6 nasłuchuje...")

        while True:
            raw_packet, addr = s.recvfrom(65535)
            print(f"\n[ZŁAPANO PAKIET] Od: {addr[0]}")
            
            # Dla RAW IPv4 musimy pominąć nagłówek IP (20B) i ICMP (8B)
            if choice == '1':
                data = raw_packet[28:]
            elif choice == '2':
                data = raw_packet # Dla SOCK_DGRAM system daje nam same dane
            else:
                data = raw_packet[8:] # Dla ICMPv6 pomijamy nagłówek ICMP

            print(f"Dane: {data.decode(errors='ignore')}")

    except PermissionError:
        print("\n[!] BŁĄD UPRAWNIEŃ!")
        print("Użyj: sudo setcap 'cap_net_raw,cap_net_bind_service+ep' $(which python3)")

# --- MENU GŁÓWNE ---

if __name__ == "__main__":
    print("--- STARTER PACK SIECIOWY (3.0 - 5.0) ---")
    mode = input("Wybierz tryb: (S)erwer / (K)lient: ").upper()
    if mode == 'S':
        run_server()
    else:
        run_client()