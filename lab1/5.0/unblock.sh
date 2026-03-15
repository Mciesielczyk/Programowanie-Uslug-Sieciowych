#!/bin/bash
echo "Zdejmowanie blokad..."

# Usuwamy regułę nr 1 tak długo, aż zdejmiemy nasze 3 blokady IPv4
# (Ponieważ po usunięciu nr 1, stara reguła nr 2 staje się nową 'jedynką')
sudo iptables -D INPUT 1
sudo iptables -D INPUT 1
sudo iptables -D INPUT 1

# Usuwamy blokadę IPv6
sudo ip6tables -D INPUT 1

echo "System odblokowany."
sudo iptables -L INPUT -n --line-numbers | head -n 6