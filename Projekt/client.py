"""
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
import ssl
from protocol import (
    wyslij, odbierz, TIMEOUT, MsgType
)

# Globalny stan klienta
moj_symbol = None       # "X" lub "O"
moja_kolej = False      # czy teraz mój ruch
gra_aktywna = False     # czy gra trwa
plansza = [["." for _ in range(3)] for _ in range(3)]


#Rysuje planszę w terminalu
def narysuj_plansze(p: list):
    print("\n  0 1 2")
    print(" -------")
    for i, rzad in enumerate(p):
        print(f"{i}| {' '.join(rzad)} |")
    print(" -------\n")


#Pyta użytkownika o ruch,zwraca (row, col) lub (-1, -1) jeśli użytkownik chce wyjść
def zapytaj_o_ruch() -> tuple[int, int]:
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

#Wątek wysyłający PING co 10 sekund
def watek_ping(sock: socket.socket):
    while gra_aktywna:
        time.sleep(10)
        if not gra_aktywna:
            break
        try:
            wyslij(sock, MsgType.PING, {})
        except ConnectionError:
            break

#Główna funkcja klienta

def polacz_i_graj(host: str, port: int):
    global moj_symbol, moja_kolej, gra_aktywna, plansza

    print(f"[KLIENT] Łączę się z {host}:{port}...")

    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False      # bo mamy self-signed cert
        context.verify_mode = ssl.CERT_NONE # j.w.
        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw_sock.connect((host, port))
        sock = context.wrap_socket(raw_sock)
        sock.settimeout(TIMEOUT)
        
        print("[KLIENT] Połączono!")
    except (ConnectionRefusedError, OSError) as e:
        print(f"[KLIENT] Nie można połączyć: {e}")
        return

    try:
        # Krok 1: Podaj login i wyślij HELLO
        login = input("Login: ").strip()
        wyslij(sock, MsgType.HELLO, {"login": login})

        # Odbierz HELLO od serwera
        wiad = odbierz(sock)
        if wiad["type"] != MsgType.HELLO:
            print(f"[KLIENT] Nieoczekiwana odpowiedź: {wiad['type']}")
            return
        print(f"[SERWER] {wiad['payload'].get('msg')}")

        # Krok 2: Logowanie (max 3 próby)
        for proba in range(3):
            haslo = input("Hasło: ").strip()
            wyslij(sock, MsgType.AUTH, {"login": login, "password": haslo})

            wiad = odbierz(sock)
            if wiad["type"] == MsgType.AUTH_OK:
                print(f"[SERWER] {wiad['payload'].get('msg')}")
                break
            elif wiad["type"] == MsgType.AUTH_ERR:
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

            if wiad["type"] == MsgType.WAIT:
                print(f"[SERWER] {wiad['payload'].get('msg')}")
                continue

            if wiad["type"] == MsgType.START:
                moj_symbol = wiad["payload"]["symbol"]
                rywal = wiad["payload"]["rywal"]
                zaczynasz = wiad["payload"]["zaczynasz"]
                print(f"\n[SERWER] Gra zaczyna się! Grasz jako {moj_symbol} przeciwko {rywal}")
                if zaczynasz:
                    print("[SERWER] Ty zaczynasz!")
                else:
                    print(f"[SERWER] {rywal} zaczyna.")
                break

            if wiad["type"] == MsgType.BYE:
                print(f"[SERWER] {wiad['payload'].get('reason', 'Rozłączono')}")
                return

            if wiad["type"] == MsgType.ERROR:
                print(f"[BŁĄD] {wiad['payload'].get('msg')}")
                return

        # Krok 4: Główna pętla gry
        gra_aktywna = True

        # Uruchom wątek ping w tle
        ping_watek = threading.Thread(target=watek_ping, args=(sock,), daemon=True)
        ping_watek.start()

        narysuj_plansze(plansza)

        while gra_aktywna:
            wiad = odbierz(sock)


            if wiad["type"] == MsgType.PONG:
                continue

            elif wiad["type"] == MsgType.BOARD:
                # Serwer wysłał nowy stan planszy
                plansza = wiad["payload"]["board"]
                ostatni_ruch = wiad["payload"].get("last_move", {})
                if ostatni_ruch:
                    print(f"\n[PLANSZA] {ostatni_ruch.get('symbol','?')} zagrał na ({ostatni_ruch.get('row')},{ostatni_ruch.get('col')})")
                narysuj_plansze(plansza)

            elif wiad["type"] == MsgType.YOUR_TURN:
                print(">>> Twoja kolej! <<<")
                row, col = zapytaj_o_ruch()

                if row == -1:
                    wyslij(sock, MsgType.BYE, {"reason": "Gracz opuścił grę"})
                    gra_aktywna = False
                else:
                    wyslij(sock, MsgType.MOVE, {"row": row, "col": col})

            elif wiad["type"] == MsgType.WIN:
                _obsluz_koniec_gry(wiad)
                gra_aktywna = False

            elif wiad["type"] == MsgType.DRAW:
                print("\n=== REMIS! ===")
                gra_aktywna = False

            elif wiad["type"] == MsgType.ERROR:
                # Jeśli serwer odrzuci ruch, wypisuje błąd
                print(f"[BŁĄD SERWERA] {wiad['payload'].get('msg')}")
                
                print("Spróbuj ponownie!")
                row, col = zapytaj_o_ruch()
                if row == -1:
                    wyslij(sock, MsgType.BYE, {"reason": "Gracz opuścił grę"})
                    gra_aktywna = False
                else:
                    wyslij(sock, MsgType.MOVE, {"row": row, "col": col})
                # Teraz pętla wróci do odbierz(sock) i będzie czekać na wynik poprawnego ruchu

            elif wiad["type"] == MsgType.BYE:
                print(f"\n[SERWER] {wiad['payload'].get('msg', 'Rozłączono')}")
                gra_aktywna = False

            elif wiad["type"] == MsgType.ERROR:
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
            wyslij(sock, MsgType.BYE, {"reason": "Klient przerwał"})
        except Exception:
            pass
    finally:
        gra_aktywna = False
        sock.close()
        print("[KLIENT] Rozłączono.")


#wyświetl wynik gry
def _obsluz_koniec_gry(wiad: dict):
    
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