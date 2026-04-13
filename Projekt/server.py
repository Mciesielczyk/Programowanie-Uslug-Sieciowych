"""
server.py — serwer gry kółko i krzyżyk
=======================================
Uruchomienie:  python server.py
"""
import select
import socket
import threading
import hashlib
import time
import sys
from protocol import (
    wyslij, odbierz, TIMEOUT,
    MSG_HELLO, MSG_AUTH, MSG_AUTH_OK, MSG_AUTH_ERR,
    MSG_WAIT, MSG_START, MSG_MOVE, MSG_BOARD,
    MSG_YOUR_TURN, MSG_WIN, MSG_DRAW, MSG_ERROR,
    MSG_BYE, MSG_PING, MSG_PONG
)

# Konfiguracja serwera
HOST = "0.0.0.0"   # słuchaj na wszystkich interfejsach
PORT = 5555

# Baza danych użytkowników
UZYTKOWNICY = {
    "gracz1": hashlib.sha256(b"haslo1").hexdigest(),
    "g1": hashlib.sha256(b"h1").hexdigest(),
    "g2": hashlib.sha256(b"h2").hexdigest(),
    "gracz2": hashlib.sha256(b"haslo2").hexdigest(),
    "gracz3": hashlib.sha256(b"haslo3").hexdigest(),
    "admin":  hashlib.sha256(b"admin123").hexdigest(),
}

poczekalnia_lock = threading.Lock()
poczekalnia = []  # lista (socket, login) czekających graczy


def hash_hasla(haslo: str) -> str:
    return hashlib.sha256(haslo.encode()).hexdigest()


def zaloguj_klienta(sock: socket.socket, addr) -> str | None:
    """Handshake i autoryzacja klienta."""
    print(f"[SERWER] Nowe połączenie od {addr}")
    try:
        wiad = odbierz(sock)
        if wiad["type"] != MSG_HELLO:
            wyslij(sock, MSG_ERROR, {"code": 400, "msg": "Oczekiwano HELLO"})
            return None

        login_z_hello = wiad["payload"].get("login", "?")
        print(f"[SERWER] HELLO od: {login_z_hello}")
        wyslij(sock, MSG_HELLO, {"msg": "Witaj! Podaj dane logowania."})

        for proba in range(3):
            wiad = odbierz(sock)
            if wiad["type"] != MSG_AUTH:
                wyslij(sock, MSG_ERROR, {"code": 400, "msg": "Oczekiwano AUTH"})
                return None

            login = wiad["payload"].get("login", "")
            haslo_hash = hash_hasla(wiad["payload"].get("password", ""))

            if UZYTKOWNICY.get(login) == haslo_hash:
                wyslij(sock, MSG_AUTH_OK, {"msg": f"Zalogowano jako {login}"})
                print(f"[SERWER] Zalogowano: {login}")
                return login
            else:
                pozostalo = 2 - proba
                wyslij(sock, MSG_AUTH_ERR, {
                    "msg": "Błędny login lub hasło",
                    "attempts_left": pozostalo
                })
                print(f"[SERWER] Nieudane logowanie dla: {login}")
        return None
    except Exception as e:
        print(f"[SERWER] Błąd logowania {addr}: {e}")
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

    def wyslij_do_obu(self, typ: str, payload: dict):
        for gracz in self.gracze:
            try: wyslij(gracz["sock"], typ, payload)
            except: pass

    def graj(self):
        # Start sesji
        for i, gracz in enumerate(self.gracze):
            rywal = self.gracze[1 - i]
            try:
                wyslij(gracz["sock"], MSG_START, {
                    "symbol": gracz["symbol"], "rywal": rywal["login"], "zaczynasz": (i == self.aktywny)
                })
            except: return

        print(f"[GRA] Mecz rozpoczęty: {self.gracze[0]['login']} (X) vs {self.gracze[1]['login']} (O)")
        wyslij(self.gracze[self.aktywny]["sock"], MSG_YOUR_TURN, {"msg": "Twoja kolej!"})

        lista_socketow = [self.gracze[0]["sock"], self.gracze[1]["sock"]]

        while True:
            readable, _, _ = select.select(lista_socketow, [], [], 0.5)
            for s in readable:
                try:
                    wiad = odbierz(s)
                    idx = 0 if s == self.gracze[0]["sock"] else 1
                    nadawca = self.gracze[idx]
                    przeciwnik = self.gracze[1 - idx]

                    if wiad["type"] == MSG_PING:
                        wyslij(s, MSG_PONG, {})
                        continue

                    if wiad["type"] == MSG_BYE:
                        print(f"[REZULTAT] {nadawca['login']} poddał się. {przeciwnik['login']} wygrywa.")
                        try: wyslij(przeciwnik["sock"], MSG_WIN, {"winner": przeciwnik["login"], "reason": "Przeciwnik poddał mecz"})
                        except: pass
                        return

                    if wiad["type"] == MSG_MOVE:
                        if idx != self.aktywny:
                            wyslij(s, MSG_ERROR, {"msg": "Czekaj na swoją kolej!"})
                            continue

                        row, col = wiad.get("payload", {}).get("row"), wiad.get("payload", {}).get("col")
                        if not (isinstance(row, int) and 0 <= row <= 2 and isinstance(col, int) and 0 <= col <= 2):
                            wyslij(s, MSG_ERROR, {"msg": "Błędne współrzędne"})
                            continue

                        if self.plansza[row][col] != ".":
                            wyslij(s, MSG_ERROR, {"msg": "To pole jest zajęte"})
                            continue

                        self.plansza[row][col] = nadawca["symbol"]
                        print(f"[GRA] {nadawca['login']} postawił {nadawca['symbol']} na ({row}, {col})")

                        self.wyslij_do_obu(MSG_BOARD, {
                            "board": self.plansza,
                            "last_move": {"row": row, "col": col, "symbol": nadawca["symbol"]}
                        })

                        zwyciezca = self.sprawdz_wygrana()
                        if zwyciezca:
                            print(f"[REZULTAT] Koniec! Zwycięzca: {nadawca['login']} ({zwyciezca})")
                            self.wyslij_do_obu(MSG_WIN, {"winner": nadawca["login"], "symbol": zwyciezca})
                            return

                        if self.sprawdz_remis():
                            print(f"[REZULTAT] Koniec! Remis pomiędzy {self.gracze[0]['login']} a {self.gracze[1]['login']}")
                            self.wyslij_do_obu(MSG_DRAW, {"msg": "Remis!"})
                            return

                        self.aktywny = 1 - self.aktywny
                        wyslij(self.gracze[self.aktywny]["sock"], MSG_YOUR_TURN, {"msg": "Twój ruch!"})

                except Exception as e:
                    idx = 0 if s == self.gracze[0]["sock"] else 1
                    przeciwnik = self.gracze[1 - idx]
                    print(f"[REZULTAT] Rozłączenie z {self.gracze[idx]['login']}. {przeciwnik['login']} wygrywa walkowerem.")
                    try: wyslij(przeciwnik["sock"], MSG_WIN, {"winner": przeciwnik["login"], "reason": "Utrata połączenia"})
                    except: pass
                    return


def obsluz_klienta(sock: socket.socket, addr):
    sock.settimeout(TIMEOUT)
    login = zaloguj_klienta(sock, addr)
    if not login:
        try: wyslij(sock, MSG_BYE, {"reason": "Błąd autoryzacji"})
        except: pass
        sock.close()
        return

    with poczekalnia_lock:
        if any(p[1] == login for p in poczekalnia):
            wyslij(sock, MSG_ERROR, {"code": 409, "msg": "Jesteś już w poczekalni"})
            sock.close()
            return

        poczekalnia.append((sock, login))
        print(f"[SERWER] {login} w poczekalni (łącznie: {len(poczekalnia)})")

        if len(poczekalnia) >= 2:
            s1, l1 = poczekalnia.pop(0)
            s2, l2 = poczekalnia.pop(0)
            gra = GraKolkoKrzyzyk(s1, l1, s2, l2)
            threading.Thread(target=gra.graj, daemon=True).start()
        else:
            wyslij(sock, MSG_WAIT, {"msg": "Czekam na przeciwnika..."})


def uruchom_serwer():
    serwer_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serwer_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serwer_sock.bind((HOST, PORT))
    serwer_sock.listen(10)
    print(f"[SERWER] Działa na {HOST}:{PORT}")
    try:
        while True:
            sock, addr = serwer_sock.accept()
            threading.Thread(target=obsluz_klienta, args=(sock, addr), daemon=True).start()
    except KeyboardInterrupt:
        print("\n[SERWER] Zamykam...")
    finally:
        serwer_sock.close()


if __name__ == "__main__":
    uruchom_serwer()