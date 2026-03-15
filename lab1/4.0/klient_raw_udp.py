import socket
import struct

# ============================================================
#  GNIAZDA SUROWE — ocena 4.0
#  Tylko klient — buduje nagłówek UDP ręcznie (SOCK_RAW)
#  Test: uruchom serwer z oceny 3.0, potem ten plik
#        serwer 3.0 powinien odebrać wiadomość normalnie
# ============================================================

def calculate_checksum(msg):
    """Suma kontrolna RFC 1071 — wymagana w nagłówkach IP i UDP"""
    if len(msg) % 2 != 0:
        msg += b'\x00'
    s = 0
    for i in range(0, len(msg), 2):
        w = (msg[i] << 8) + (msg[i + 1])
        s += w
    s = (s >> 16) + (s & 0xffff)
    return ~s & 0xffff


def build_ip_header(src_ip, dst_ip, data_length):
    """
    Buduje nagłówek IP (20 bajtów).
    Pola nagłówka IP (RFC 791):
      - Wersja + IHL : 1B  (0x45 = IPv4, nagłówek = 20B)
      - DSCP/ECN     : 1B  (0 = brak priorytetu)
      - Długość całk.: 2B  (IP + UDP + dane)
      - Identyfikator: 2B  (numer pakietu, dowolny)
      - Flagi+Offset : 2B  (0 = bez fragmentacji)
      - TTL          : 1B  (64 = standardowa wartość)
      - Protokół     : 1B  (17 = UDP)
      - Checksum     : 2B  (najpierw 0, potem obliczamy)
      - IP źródłowy  : 4B
      - IP docelowy  : 4B
    """
    version_ihl  = 0x45
    dscp_ecn     = 0
    total_len    = 20 + 8 + data_length
    packet_id    = 54321
    flags_offset = 0
    ttl          = 64
    protocol     = socket.IPPROTO_UDP
    checksum     = 0
    src          = socket.inet_aton(src_ip)
    dst          = socket.inet_aton(dst_ip)

    header = struct.pack('!BBHHHBBH4s4s',
                         version_ihl, dscp_ecn, total_len,
                         packet_id, flags_offset,
                         ttl, protocol, checksum,
                         src, dst)

    checksum = calculate_checksum(header)
    header = struct.pack('!BBHHHBBH4s4s',
                         version_ihl, dscp_ecn, total_len,
                         packet_id, flags_offset,
                         ttl, protocol, checksum,
                         src, dst)
    return header


def build_udp_header(src_port, dst_port, data, src_ip, dst_ip):
    """
    Buduje nagłówek UDP (8 bajtów).
    Pola nagłówka UDP (RFC 768):
      - Port źródłowy : 2B
      - Port docelowy : 2B
      - Długość       : 2B  (nagłówek UDP + dane)
      - Checksum      : 2B  (liczony z pseudo-nagłówkiem IP)

    Checksum UDP wymaga pseudo-nagłówka IP — fragmentu nagłówka IP
    używanego tylko do obliczeń, nie wysyłanego w pakiecie.
    """
    length = 8 + len(data)

    pseudo_header = struct.pack('!4s4sBBH',
                                socket.inet_aton(src_ip),
                                socket.inet_aton(dst_ip),
                                0,
                                socket.IPPROTO_UDP,
                                length)

    udp_header = struct.pack('!HHHH', src_port, dst_port, length, 0)
    checksum   = calculate_checksum(pseudo_header + udp_header + data)
    udp_header = struct.pack('!HHHH', src_port, dst_port, length, checksum)
    return udp_header


# ------------------------------------------------------------
#  KLIENT — surowe gniazdo, ręcznie zbudowany pakiet IP + UDP
# ------------------------------------------------------------

src_ip   = "127.0.0.1"
dst_ip   = "127.0.0.1"
src_port = 9999
dst_port = 22222          # musi być ten sam port co w serwerze 3.0!
message  = b"Hej z surowego gniazda!"

# SOCK_RAW + IPPROTO_RAW = budujemy nagłówek IP sami
s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)

# IP_HDRINCL = "nagłówek IP dostarczam sam, nie dodawaj swojego"
s.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)

ip_header  = build_ip_header(src_ip, dst_ip, len(message))
udp_header = build_udp_header(src_port, dst_port, message, src_ip, dst_ip)
packet     = ip_header + udp_header + message

s.sendto(packet, (dst_ip, 0))
print(f"Wysłano surowy pakiet UDP na {dst_ip}:{dst_port}")
print(f"Dane: {message.decode()}")
s.close()