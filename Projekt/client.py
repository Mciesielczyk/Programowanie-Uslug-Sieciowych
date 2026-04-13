"""
client.py — klient gry kółko i krzyżyk
========================================
Uruchomienie:  python client.py
               python client.py --host 127.0.0.1 --port 5555
"""

import socket
import threading
import argparse
import sys
import time
from protocol import (
    wyslij, odbierz, TIMEOUT,
    MSG_HELLO, MSG_AUTH, MSG_AUTH_OK, MSG_AUTH_ERR,
    MSG_WAIT, MSG_START, MSG_MOVE, MSG_BOARD,
    MSG_YOUR_TURN, MSG_WIN, MSG_DRAW, MSG_ERROR,
    MSG_BYE, MSG_PING, MSG_PONG
)

# Globalny stan klienta
moj_symbol = None       # "X" lub "O"
gra_aktywna = False     # czy gra trwa
plansza = [["." for _ in range(3)] for _ in range(3)]


def narysuj_plansze(p: list):
    """Rysuje planszę w terminalu w ładny sposób."""
    print("\n   0 1 2")
    print(" -------")
    for i, rzad in enumerate(p):
        print(f"{i}| {' '.join(rzad)} |")
    print(" -------\n")


def zapytaj_o_ruch() -> tuple[int, int]:
    """Pyta użytkownika o ruch. Zwraca (row, col) lub (-1, -1)."""
    while True:
        try:
            wejscie = input("Twój ruch (wiersz kolumna, np. '1 2', lub 'q' żeby wyjść): ").strip()
            if wejscie.lower() == 'q':
                return -1, -1
            czesci = wejscie.split()
            if len(czesci) != 2:
                print("Podaj dwie liczby oddzielone spacją, np. '0 1'")
                continue
            row, col = int(czesci[0]), int(czesci[1])
            if not (0 <= row <= 2 and 0 <= col <= 2):
                print("Liczby muszą być z zakresu 0-2")
                continue
            return row, col
        except ValueError:
            print("Podaj poprawne liczby całkowite")


def watek_ping(sock: socket.socket):
    """Wątek wysyłający PING co 10 sekund."""
    while gra_aktywna:
        time.sleep(10)
        if not gra_aktywna:
            break
        try:
            wyslij(sock, MSG_PING, {})
        except ConnectionError:
            break


def polacz_i_graj(host: str, port: int):
    """Główna funkcja klienta."""
    global moj_symbol, gra_aktywna, plansza

    print(f"[KLIENT] Łączę się z {host}:{port}...")

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(TIMEOUT)
        sock.connect((host, port))
        print("[KLIENT] Połączono!")
    except (ConnectionRefusedError, OSError) as e:
        print(f"[KLIENT] Nie można połączyć: {e}")
        return

    try:
        # Krok 1: Powitanie
        login = input("Login: ").strip()
        wyslij(sock, MSG_HELLO, {"login": login})
        wiad = odbierz(sock)
        if wiad["type"] != MSG_HELLO:
            print(f"[KLIENT] Nieoczekiwana odpowiedź: {wiad['type']}")
            return
        print(f"[SERWER] {wiad['payload'].get('msg')}")

        # Krok 2: Logowanie (max 3 próby)
        zalogowano = False
        for proba in range(3):
            haslo = input("Hasło: ").strip()
            wyslij(sock, MSG_AUTH, {"login": login, "password": haslo})
            wiad = odbierz(sock)
            if wiad["type"] == MSG_AUTH_OK:
                print(f"[SERWER] {wiad['payload'].get('msg')}")
                zalogowano = True
                break
            elif wiad["type"] == MSG_AUTH_ERR:
                pozostalo = wiad["payload"].get("attempts_left", 0)
                print(f"[SERWER] Błąd logowania. Pozostało prób: {pozostalo}")
                if pozostalo == 0: return
        
        if not zalogowano: return

        # Krok 3: Oczekiwanie na start
        print("[KLIENT] Szukam przeciwnika...")
        while True:
            wiad = odbierz(sock)
            if wiad["type"] == MSG_WAIT:
                print(f"[SERWER] {wiad['payload'].get('msg')}")
                continue
            if wiad["type"] == MSG_START:
                moj_symbol = wiad["payload"]["symbol"]
                rywal = wiad["payload"]["rywal"]
                zaczynasz = wiad["payload"]["zaczynasz"]
                print(f"\n[SERWER] Gra zaczyna się! Grasz jako {moj_symbol} przeciwko {rywal}")
                if zaczynasz: print("[SERWER] Ty zaczynasz!")
                else: print(f"[SERWER] {rywal} zaczyna.")
                break

        # Krok 4: Pętla gry
        gra_aktywna = True
        threading.Thread(target=watek_ping, args=(sock,), daemon=True).start()
        narysuj_plansze(plansza)

        while gra_aktywna:
            wiad = odbierz(sock)

            if wiad["type"] == MSG_PONG:
                continue

            elif wiad["type"] == MSG_BOARD:
                plansza = wiad["payload"]["board"]
                ostatni_ruch = wiad["payload"].get("last_move", {})
                if ostatni_ruch:
                    print(f"\n[PLANSZA] {ostatni_ruch.get('symbol','?')} na ({ostatni_ruch.get('row')},{ostatni_ruch.get('col')})")
                narysuj_plansze(plansza)

            elif wiad["type"] == MSG_YOUR_TURN:
                print(">>> Twoja kolej! <<<")
                row, col = zapytaj_o_ruch()
                if row == -1:
                    wyslij(sock, MSG_BYE, {"reason": "Gracz opuścił grę"})
                    gra_aktywna = False
                else:
                    wyslij(sock, MSG_MOVE, {"row": row, "col": col})

            elif wiad["type"] == MSG_ERROR:
                print(f"\n⚠️  [BŁĄD RUCHU] {wiad['payload'].get('msg')}")
                # Zamiast tylko wypisać błąd, od razu pytamy o nową pozycję
                print("Spróbuj ponownie teraz:")
                row, col = zapytaj_o_ruch()
                if row == -1:
                    wyslij(sock, MSG_BYE, {"reason": "Gracz opuścił grę"})
                    gra_aktywna = False
                else:
                    wyslij(sock, MSG_MOVE, {"row": row, "col": col})

            elif wiad["type"] == MSG_WIN:
                _obsluz_koniec_gry(wiad)
                gra_aktywna = False

            elif wiad["type"] == MSG_DRAW:
                print("\n=== REMIS! ===")
                gra_aktywna = False

            elif wiad["type"] == MSG_BYE:
                print(f"\n[SERWER] {wiad['payload'].get('msg', 'Rozłączono')}")
                gra_aktywna = False

    except (TimeoutError, ConnectionError, ValueError) as e:
        print(f"[KLIENT] Błąd: {e}")
    except KeyboardInterrupt:
        print("\n[KLIENT] Przerwanie...")
    finally:
        gra_aktywna = False
        sock.close()
        print("[KLIENT] Rozłączono.")


def _obsluz_koniec_gry(wiad: dict):
    global moj_symbol
    winner = wiad["payload"].get("winner", "")
    symbol = wiad["payload"].get("symbol", "")
    print("\n" + "="*30)
    if symbol == moj_symbol: print(f"🎉 WYGRAŁEŚ! ({winner})")
    else: print(f"😞 Przegrałeś. Wygrał: {winner}")
    print("="*30 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5555)
    args = parser.parse_args()
    polacz_i_graj(args.host, args.port)