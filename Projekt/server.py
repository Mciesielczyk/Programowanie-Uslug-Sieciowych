"""
server.py — serwer gry kółko i krzyżyk
=======================================
Uruchomienie:  python server.py

Co robi serwer:
  1. Czeka na połączenia od klientów
  2. Każdy klient musi się zalogować (AUTH)
  3. Czeka aż dołączą 2 gracze, potem startuje grę
  4. Kolejno przyjmuje ruchy i rozsyła stan planszy
  5. Wykrywa wygraną / remis i kończy sesję

Serwer obsługuje wiele gier jednocześnie (każda para graczy w osobnym wątku).
"""
import select
import socket
import threading
import hashlib
import time
import sys
import ssl
from protocol import (
    wyslij, odbierz, TIMEOUT, MsgType
)

# Konfiguracja serwera
HOST = "0.0.0.0"   # słuchaj na wszystkich interfejsach
PORT = 5555

# Prosta "baza danych" użytkowników: login -> hash_hasla
# W prawdziwej apce byłaby prawdziwa baza danych
UZYTKOWNICY = {
    "gracz1": hashlib.sha256(b"haslo1").hexdigest(),
    "gracz2": hashlib.sha256(b"haslo2").hexdigest(),
    "gracz3": hashlib.sha256(b"haslo3").hexdigest(),
    "admin":  hashlib.sha256(b"admin123").hexdigest(),

    "a1": hashlib.sha256(b"a").hexdigest(),
    "b1": hashlib.sha256(b"b").hexdigest(),
    "x1": hashlib.sha256(b"x").hexdigest(),
    "y1": hashlib.sha256(b"y").hexdigest(),

    "a2": hashlib.sha256(b"a").hexdigest(),
    "b2": hashlib.sha256(b"b").hexdigest(),
    "x2": hashlib.sha256(b"x").hexdigest(),
    "y2": hashlib.sha256(b"y").hexdigest(),

    "a3": hashlib.sha256(b"a").hexdigest(),
    "b3": hashlib.sha256(b"b").hexdigest(),
    "x3": hashlib.sha256(b"x").hexdigest(),
    "y3": hashlib.sha256(b"y").hexdigest(),
}

# Poczekalnia — tu trafiają zalogowani gracze czekający na rywala
# Lock potrzebny bo wiele wątków może próbować dołączyć jednocześnie
poczekalnia_lock = threading.Lock()
poczekalnia = []  # lista (socket, login) czekających graczy


def hash_hasla(haslo: str) -> str:
    return hashlib.sha256(haslo.encode()).hexdigest()


def zaloguj_klienta(sock: socket.socket, addr) -> str | None:
    """Handshake i autoryzacja z użyciem MsgType."""
    print(f"[SERWER] Nowe połączenie od {addr}")

    try:
        # Krok 1: Oczekiwanie na HELLO
        wiad = odbierz(sock)
        if wiad["type"] != MsgType.HELLO:
            wyslij(sock, MsgType.ERROR, {"code": 400, "msg": "Oczekiwano HELLO"})
            return None

        login_z_hello = wiad["payload"].get("login", "?")
        print(f"[SERWER] HELLO od: {login_z_hello}")
        wyslij(sock, MsgType.HELLO, {"msg": "Witaj! Podaj dane logowania."})

        # Krok 2: Próby logowania (max 3)
        for proba in range(3):
            wiad = odbierz(sock)
            if wiad["type"] != MsgType.AUTH:
                wyslij(sock, MsgType.ERROR, {"code": 400, "msg": "Oczekiwano AUTH"})
                return None

            login = wiad["payload"].get("login", "")
            haslo_hash = hash_hasla(wiad["payload"].get("password", ""))

            if UZYTKOWNICY.get(login) == haslo_hash:
                wyslij(sock, MsgType.AUTH_OK, {"msg": f"Zalogowano jako {login}"})
                print(f"[SERWER] Zalogowano pomyślnie: {login}")
                return login
            else:
                pozostalo = 2 - proba
                wyslij(sock, MsgType.AUTH_ERR, {
                    "msg": "Błędny login lub hasło",
                    "attempts_left": pozostalo
                })
                print(f"[SERWER] Nieudane logowanie ({proba+1}/3) dla: {login}")

        return None

    except (ConnectionError, TimeoutError, ValueError) as e:
        print(f"[SERWER] Błąd autoryzacji {addr}: {e}")
        return None


class GraKolkoKrzyzyk:
    def __init__(self, sock1, login1, sock2, login2):
        self.gracze = [
            {"sock": sock1, "login": login1, "symbol": "X"},
            {"sock": sock2, "login": login2, "symbol": "O"},
        ]
        self.plansza = [["." for _ in range(3)] for _ in range(3)]
        self.aktywny = 0 

    def sprawdz_wygrana(self) -> str | None:
        p = self.plansza
        linie = [
            [p[0][0], p[0][1], p[0][2]], [p[1][0], p[1][1], p[1][2]], [p[2][0], p[2][1], p[2][2]],
            [p[0][0], p[1][0], p[2][0]], [p[0][1], p[1][1], p[2][1]], [p[0][2], p[1][2], p[2][2]],
            [p[0][0], p[1][1], p[2][2]], [p[0][2], p[1][1], p[2][0]]
        ]
        for linia in linie:
            if linia[0] != "." and linia[0] == linia[1] == linia[2]:
                return linia[0]
        return None

    def sprawdz_remis(self) -> bool:
        return all(pole != "." for rzad in self.plansza for pole in rzad)

    def wyslij_do_obu(self, typ: MsgType, payload: dict):
        for gracz in self.gracze:
            try: wyslij(gracz["sock"], typ, payload)
            except: pass

    def graj(self):
        # Start sesji
        for i, gracz in enumerate(self.gracze):
            rywal = self.gracze[1 - i]
            try:
                wyslij(gracz["sock"], MsgType.START, {
                    "symbol": gracz["symbol"], 
                    "rywal": rywal["login"], 
                    "zaczynasz": (i == self.aktywny)
                })
            except: return

        # INFO NA SERWERZE O STARCIE
        print(f"\n[MECZ] Rozpoczęto: {self.gracze[0]['login']} (X) vs {self.gracze[1]['login']} (O)")
        
        wyslij(self.gracze[self.aktywny]["sock"], MsgType.YOUR_TURN, {"msg": "Twój ruch!"})

        lista_socketow = [self.gracze[0]["sock"], self.gracze[1]["sock"]]

        while True:
            readable, _, _ = select.select(lista_socketow, [], [], 0.5)
            for s in readable:
                try:
                    wiad = odbierz(s)
                    idx = 0 if s == self.gracze[0]["sock"] else 1
                    nadawca = self.gracze[idx]
                    przeciwnik = self.gracze[1 - idx]

                    if wiad["type"] == MsgType.PING:
                        wyslij(s, MsgType.PONG, {})
                        continue

                    if wiad["type"] == MsgType.BYE:
                        # INFO NA SERWERZE O UCIECZCE
                        print(f"[REZULTAT] Gracz {nadawca['login']} poddał mecz.")
                        try: 
                            wyslij(przeciwnik["sock"], MsgType.WIN, {
                                "winner": przeciwnik["login"], 
                                "reason": "Rywal poddał mecz"
                            })
                        except: pass
                        return

                    if wiad["type"] == MsgType.MOVE:
                        if idx != self.aktywny:
                            wyslij(s, MsgType.ERROR, {"msg": "To nie Twój ruch!"})
                            continue

                        p = wiad.get("payload", {})
                        row, col = p.get("row"), p.get("col")

                        # Walidacja
                        if not (isinstance(row, int) and 0 <= row <= 2 and isinstance(col, int) and 0 <= col <= 2):
                            wyslij(s, MsgType.ERROR, {"msg": "Złe pole!"})
                            continue
                        if self.plansza[row][col] != ".":
                            wyslij(s, MsgType.ERROR, {"msg": "Pole zajęte!"})
                            continue

                        # WYKONANIE RUCHU I INFO NA SERWERZE
                        self.plansza[row][col] = nadawca["symbol"]
                        print(f"[RUCH] {nadawca['login']} ({nadawca['symbol']}) stawia na: [{row}, {col}]")

                        self.wyslij_do_obu(MsgType.BOARD, {
                            "board": self.plansza,
                            "last_move": {"row": row, "col": col, "symbol": nadawca["symbol"]}
                        })

                        # SPRAWDZANIE WYNIKU I INFO NA SERWERZE
                        zwyciezca_symbol = self.sprawdz_wygrana()
                        if zwyciezca_symbol:
                            print(f"[KONIEC] Wygrał: {nadawca['login']} ({zwyciezca_symbol})")
                            self.wyslij_do_obu(MsgType.WIN, {
                                "winner": nadawca["login"], 
                                "symbol": zwyciezca_symbol
                            })
                            return

                        if self.sprawdz_remis():
                            print(f"[KONIEC] Remis w meczu {self.gracze[0]['login']} vs {self.gracze[1]['login']}")
                            self.wyslij_do_obu(MsgType.DRAW, {"msg": "Remis!"})
                            return

                        # ZMIANA TURY
                        self.aktywny = 1 - self.aktywny
                        wyslij(self.gracze[self.aktywny]["sock"], MsgType.YOUR_TURN, {"msg": "Twój ruch!"})

                except Exception as e:
                    idx = 0 if s == self.gracze[0]["sock"] else 1
                    przeciwnik = self.gracze[1 - idx]
                    print(f"[BŁĄD] Nagłe rozłączenie gracza: {self.gracze[idx]['login']}")
                    try: 
                        wyslij(przeciwnik["sock"], MsgType.WIN, {
                            "winner": przeciwnik["login"], 
                            "reason": "Przeciwnik stracił połączenie"
                        })
                    except: pass
                    return

def obsluz_klienta(sock: socket.socket, addr):
    sock.settimeout(TIMEOUT)
    login = zaloguj_klienta(sock, addr)
    if not login:
        try: wyslij(sock, MsgType.BYE, {"reason": "Błąd autoryzacji"})
        except: pass
        sock.close()
        return

    with poczekalnia_lock:
        if any(p[1] == login for p in poczekalnia):
            wyslij(sock, MsgType.ERROR, {"code": 409, "msg": "Już jesteś w kolejce!"})
            sock.close()
            return

        poczekalnia.append((sock, login))
        if len(poczekalnia) >= 2:
            s1, l1 = poczekalnia.pop(0)
            s2, l2 = poczekalnia.pop(0)
            threading.Thread(target=GraKolkoKrzyzyk(s1, l1, s2, l2).graj, daemon=True).start()
        else:
            wyslij(sock, MsgType.WAIT, {"msg": "Szukam rywala..."})

def uruchom_serwer():
    serwer_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serwer_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serwer_sock.bind((HOST, PORT))
    
    # Konfiguracja TLS
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    try:
        context.load_cert_chain("server.crt", "server.key")
    except FileNotFoundError:
        print("[BŁĄD] Brak plików certyfikatów server.crt/key!")
        return

    serwer_sock.listen(10)
    serwer_sock.settimeout(1.0) # Pozwala na Ctrl+C
    print(f"[SERWER] Działa na {HOST}:{PORT} (SSL/TLS ON)")

    try:
        while True:
            try:
                raw_sock, addr = serwer_sock.accept()
                sock = context.wrap_socket(raw_sock, server_side=True)
                threading.Thread(target=obsluz_klienta, args=(sock, addr), daemon=True).start()
            except socket.timeout:
                continue
            except ssl.SSLError as e:
                print(f"[SERWER] Błąd SSL Handshake: {e}")
    except KeyboardInterrupt:
        print("\n[SERWER] Zatrzymywanie...")
    finally:
        serwer_sock.close()


if __name__ == "__main__":
    uruchom_serwer()