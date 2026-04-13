"""
client.py — klient gry kółko i krzyżyk
========================================
Uruchomienie:  python client.py
               python client.py --host 192.168.1.10 --port 5555

Co robi klient:
  1. Łączy się z serwerem
  2. Prosi o login i hasło
  3. Czeka na drugiego gracza
  4. Pokazuje planszę i przyjmuje ruchy od użytkownika
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
moja_kolej = False      # czy teraz mój ruch
gra_aktywna = False     # czy gra trwa
plansza = [["." for _ in range(3)] for _ in range(3)]


def narysuj_plansze(p: list):
    """Rysuje planszę w terminalu w ładny sposób."""
    print("\n  0 1 2")
    print(" -------")
    for i, rzad in enumerate(p):
        print(f"{i}| {' '.join(rzad)} |")
    print(" -------\n")


def zapytaj_o_ruch() -> tuple[int, int]:
    """
    Pyta użytkownika o ruch.
    Zwraca (row, col) lub (-1, -1) jeśli użytkownik chce wyjść.
    """
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
    """
    Wątek wysyłający PING co 10 sekund żeby serwer wiedział że żyjemy.
    Działa w tle przez całą grę.
    """
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
    global moj_symbol, moja_kolej, gra_aktywna, plansza

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
        # Krok 1: Podaj login i wyślij HELLO
        login = input("Login: ").strip()
        wyslij(sock, MSG_HELLO, {"login": login})

        # Odbierz HELLO od serwera
        wiad = odbierz(sock)
        if wiad["type"] != MSG_HELLO:
            print(f"[KLIENT] Nieoczekiwana odpowiedź: {wiad['type']}")
            return
        print(f"[SERWER] {wiad['payload'].get('msg')}")

        # Krok 2: Logowanie (max 3 próby)
        for proba in range(3):
            haslo = input("Hasło: ").strip()
            wyslij(sock, MSG_AUTH, {"login": login, "password": haslo})

            wiad = odbierz(sock)
            if wiad["type"] == MSG_AUTH_OK:
                print(f"[SERWER] {wiad['payload'].get('msg')}")
                break
            elif wiad["type"] == MSG_AUTH_ERR:
                pozostalo = wiad["payload"].get("attempts_left", 0)
                print(f"[SERWER] Błąd logowania. Pozostało prób: {pozostalo}")
                if pozostalo == 0:
                    print("[KLIENT] Zbyt wiele nieudanych prób. Rozłączam.")
                    return
            else:
                print(f"[KLIENT] Nieoczekiwana odpowiedź: {wiad['type']}")
                return

        # Krok 3: Czekaj na start gry
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
                if zaczynasz:
                    print("[SERWER] Ty zaczynasz!")
                else:
                    print(f"[SERWER] {rywal} zaczyna.")
                break

            if wiad["type"] == MSG_BYE:
                print(f"[SERWER] {wiad['payload'].get('reason', 'Rozłączono')}")
                return

            if wiad["type"] == MSG_ERROR:
                print(f"[BŁĄD] {wiad['payload'].get('msg')}")
                return

        # Krok 4: Główna pętla gry
# Krok 4: Główna pętla gry
        gra_aktywna = True

        # Uruchom wątek ping w tle
        ping_watek = threading.Thread(target=watek_ping, args=(sock,), daemon=True)
        ping_watek.start()

        narysuj_plansze(plansza)

        while gra_aktywna:
            wiad = odbierz(sock)

            if wiad["type"] == MSG_PONG:
                continue

            elif wiad["type"] == MSG_BOARD:
                # Serwer wysłał nowy stan planszy
                plansza = wiad["payload"]["board"]
                ostatni_ruch = wiad["payload"].get("last_move", {})
                if ostatni_ruch:
                    print(f"\n[PLANSZA] {ostatni_ruch.get('symbol','?')} zagrał na ({ostatni_ruch.get('row')},{ostatni_ruch.get('col')})")
                narysuj_plansze(plansza)

            elif wiad["type"] == MSG_YOUR_TURN:
                # Moja kolej: Pytamy o ruch RAZ i wysyłamy. 
                # Nie robimy tu wewnętrznego odbierz(sock)!
                print(">>> Twoja kolej! <<<")
                row, col = zapytaj_o_ruch()

                if row == -1:
                    wyslij(sock, MSG_BYE, {"reason": "Gracz opuścił grę"})
                    gra_aktywna = False
                else:
                    wyslij(sock, MSG_MOVE, {"row": row, "col": col})
                    # Po wysłaniu ruchu pętla wraca na górę do wiad = odbierz(sock)
                    # i tam czeka na MSG_BOARD (sukces) lub MSG_ERROR (zły ruch)

            elif wiad["type"] == MSG_WIN:
                _obsluz_koniec_gry(wiad)
                gra_aktywna = False

            elif wiad["type"] == MSG_DRAW:
                print("\n=== REMIS! ===")
                gra_aktywna = False

            elif wiad["type"] == MSG_ERROR:
                # Jeśli serwer odrzuci ruch, wypisujemy błąd.
                # Ponieważ tura na serwerze się nie zmieniła, 
                # serwer zaraz wyśle ponownie MSG_YOUR_TURN, co wywoła zapytaj_o_ruch()
                print(f"[BŁĄD SERWERA] {wiad['payload'].get('msg')}")

            elif wiad["type"] == MSG_BYE:
                print(f"\n[SERWER] {wiad['payload'].get('msg', 'Rozłączono')}")
                gra_aktywna = False

            elif wiad["type"] == MSG_WIN:
                _obsluz_koniec_gry(wiad)
                gra_aktywna = False

            elif wiad["type"] == MSG_DRAW:
                print("\n=== REMIS! ===")
                gra_aktywna = False

            elif wiad["type"] == MSG_BYE:
                print(f"\n[SERWER] {wiad['payload'].get('msg', 'Rozłączono')}")
                gra_aktywna = False

            elif wiad["type"] == MSG_ERROR:
                print(f"[BŁĄD SERWERA] {wiad['payload'].get('msg')}")

    except TimeoutError:
        print("[KLIENT] Timeout — serwer nie odpowiada")
    except ConnectionError as e:
        print(f"[KLIENT] Utrata połączenia: {e}")
    except ValueError as e:
        print(f"[KLIENT] Błąd protokołu: {e}")
    except KeyboardInterrupt:
        print("\n[KLIENT] Przerywam...")
        try:
            wyslij(sock, MSG_BYE, {"reason": "Klient przerwał"})
        except Exception:
            pass
    finally:
        gra_aktywna = False
        sock.close()
        print("[KLIENT] Rozłączono.")


def _obsluz_koniec_gry(wiad: dict):
    """Wyświetla wynik gry."""
    global moj_symbol
    winner = wiad["payload"].get("winner", "")
    reason = wiad["payload"].get("reason", "")
    symbol = wiad["payload"].get("symbol", "")

    print("\n" + "="*30)
    # Żeby sprawdzić czy wygrałem muszę porównać symbol
    if symbol == moj_symbol or (not symbol and winner):
        print(f"🎉 WYGRAŁEŚ! ({winner})")
    else:
        print(f"😞 Przegrałeś. Wygrał: {winner}")
    if reason:
        print(f"Powód: {reason}")
    print("="*30 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Klient kółko i krzyżyk")
    parser.add_argument("--host", default="127.0.0.1", help="Adres serwera")
    parser.add_argument("--port", type=int, default=5555, help="Port serwera")
    args = parser.parse_args()

    polacz_i_graj(args.host, args.port)