#!/bin/bash
echo "Nakładanie blokad firewall..."

# Blokada IPv4
sudo iptables -I INPUT 1 -p tcp --dport 12345 -j DROP
sudo iptables -I INPUT 1 -i lo -p tcp --dport 12345 -j DROP
sudo iptables -I INPUT 1 -p udp --dport 22222 -j DROP

# Blokada IPv6
sudo ip6tables -I INPUT 1 -p tcp --dport 12345 -j DROP

echo "Status iptables (4 pierwsze linie):"
sudo iptables -L INPUT -n --line-numbers | head -n 6
echo "Blokada aktywna."