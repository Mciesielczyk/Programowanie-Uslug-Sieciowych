import socket, struct

def checksum(msg):
    if len(msg) % 2: msg += b'\x00'
    s = sum((msg[i] << 8) + msg[i+1] for i in range(0, len(msg), 2))
    s = (s >> 16) + (s & 0xffff)
    return ~s & 0xffff

src_ip, dst_ip = "127.0.0.1", "127.0.0.1"
sport, dport   = 9999, 22222
data           = b"Hej z surowego gniazda!"

# nagłówek IP
iph = struct.pack('!BBHHHBBH4s4s', 0x45, 0, 20+8+len(data), 1, 0, 64,
                  socket.IPPROTO_UDP, 0, socket.inet_aton(src_ip), socket.inet_aton(dst_ip))
                  
iph = struct.pack('!BBHHHBBH4s4s', 0x45, 0, 20+8+len(data), 1, 0, 64,
                  socket.IPPROTO_UDP, checksum(iph), socket.inet_aton(src_ip), socket.inet_aton(dst_ip))

# nagłówek UDP
udph = struct.pack('!HHHH', sport, dport, 8+len(data), 0)

pseudo = struct.pack('!4s4sBBH', socket.inet_aton(src_ip), socket.inet_aton(dst_ip),
                     0, socket.IPPROTO_UDP, 8+len(data))

udph = struct.pack('!HHHH', sport, dport, 8+len(data), checksum(pseudo + udph + data))

s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
s.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
s.sendto(iph + udph + data, (dst_ip, 0))
print("Wysłano!")