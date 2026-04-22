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
    wyslij, odbierz, TIMEOUT,
    MSG_HELLO, MSG_AUTH, MSG_AUTH_OK, MSG_AUTH_ERR,
    MSG_WAIT, MSG_START, MSG_MOVE, MSG_BOARD,
    MSG_YOUR_TURN, MSG_WIN, MSG_DRAW, MSG_ERROR,
    MSG_BYE, MSG_PING, MSG_PONG
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
}

# Poczekalnia — tu trafiają zalogowani gracze czekający na rywala
# Lock potrzebny bo wiele wątków może próbować dołączyć jednocześnie
poczekalnia_lock = threading.Lock()
poczekalnia = []  # lista (socket, login) czekających graczy


def hash_hasla(haslo: str) -> str:
    return hashlib.sha256(haslo.encode()).hexdigest()


def zaloguj_klienta(sock: socket.socket, addr) -> str | None:
    """
    Przeprowadza handshake i autoryzację.
    Zwraca login jeśli sukces, None jeśli błąd.
    Klient ma 3 próby logowania.
    """
    print(f"[SERWER] Nowe połączenie od {addr}")

    try:
        # Krok 1: Czekamy na HELLO
        wiad = odbierz(sock)
        if wiad["type"] != MSG_HELLO:
            wyslij(sock, MSG_ERROR, {"code": 400, "msg": "Oczekiwano HELLO"})
            return None

        login_z_hello = wiad["payload"].get("login", "?")
        print(f"[SERWER] HELLO od: {login_z_hello}")
        wyslij(sock, MSG_HELLO, {"msg": "Witaj! Podaj dane logowania."})

        # Krok 2: Próby logowania (max 3)
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

        print(f"[SERWER] Zbyt wiele nieudanych prób od {addr}")
        return None

    except (ConnectionError, TimeoutError, ValueError) as e:
        print(f"[SERWER] Błąd podczas logowania {addr}: {e}")
        return None


class GraKolkoKrzyzyk:
    """
    Logika jednej rozgrywki między dwoma graczami.
    Każda gra działa w osobnym wątku.
    """

    def __init__(self, sock1, login1, sock2, login2):
        self.gracze = [
            {"sock": sock1, "login": login1, "symbol": "X"},
            {"sock": sock2, "login": login2, "symbol": "O"},
        ]
        # Plansza 3x3, pusta na starcie
        self.plansza = [["." for _ in range(3)] for _ in range(3)]
        self.aktywny = 0  # indeks gracza który teraz rusza (0 lub 1)

    def plansza_jako_string(self) -> str:
        """Zamienia planszę na string do wysłania."""
        return "\n".join([" ".join(rzad) for rzad in self.plansza])

    def plansza_jako_lista(self) -> list:
        return self.plansza

    def sprawdz_wygrana(self) -> str | None:
        """
        Sprawdza czy ktoś wygrał.
        Zwraca symbol wygrywającego (X lub O) albo None.
        """
        p = self.plansza
        # Sprawdź wiersze, kolumny i przekątne
        linie = [
            [p[0][0], p[0][1], p[0][2]],  # wiersz 0
            [p[1][0], p[1][1], p[1][2]],  # wiersz 1
            [p[2][0], p[2][1], p[2][2]],  # wiersz 2
            [p[0][0], p[1][0], p[2][0]],  # kolumna 0
            [p[0][1], p[1][1], p[2][1]],  # kolumna 1
            [p[0][2], p[1][2], p[2][2]],  # kolumna 2
            [p[0][0], p[1][1], p[2][2]],  # przekątna
            [p[0][2], p[1][1], p[2][0]],  # przekątna
        ]
        for linia in linie:
            if linia[0] != "." and linia[0] == linia[1] == linia[2]:
                return linia[0]
        return None

    def sprawdz_remis(self) -> bool:
        """Sprawdza czy plansza jest pełna (remis)."""
        return all(pole != "." for rzad in self.plansza for pole in rzad)

    def wyslij_do_obu(self, typ: str, payload: dict):
        """Wysyła tę samą wiadomość do obu graczy."""
        for gracz in self.gracze:
            try:
                wyslij(gracz["sock"], typ, payload)
            except ConnectionError:
                pass  # jeden z graczy mógł się rozłączyć

    def graj(self):
            """
            Główna pętla gry z użyciem select. 
            Obsługuje ruchy, pingi i rozłączenia od obu graczy w czasie rzeczywistym.
            """
            # 1. Poinformuj obu graczy o starcie sesji
            for i, gracz in enumerate(self.gracze):
                rywal = self.gracze[1 - i]
                try:
                    wyslij(gracz["sock"], MSG_START, {
                        "symbol": gracz["symbol"],
                        "rywal": rywal["login"],
                        "zaczynasz": (i == self.aktywny)
                    })
                except ConnectionError:
                    print(f"[GRA] Błąd startu dla {gracz['login']}")
                    return

            print(f"[GRA] Mecz rozpoczęty: {self.gracze[0]['login']} (X) vs {self.gracze[1]['login']} (O)")
            
            # Powiedz pierwszemu graczowi, że czas na ruch
            wyslij(self.gracze[self.aktywny]["sock"], MSG_YOUR_TURN, {"msg": "Twoja kolej!"})

            # Lista socketów do monitorowania przez select
            lista_socketow = [self.gracze[0]["sock"], self.gracze[1]["sock"]]

            while True:
                # select sprawdza, czy na którymś gnieździe pojawiły się dane (timeout 0.5s)
                readable, _, _ = select.select(lista_socketow, [], [], 0.5)

                for s in readable:
                    try:
                        wiad = odbierz(s)
                        
                        # Identyfikacja gracza
                        idx_nadawcy = 0 if s == self.gracze[0]["sock"] else 1
                        nadawca = self.gracze[idx_nadawcy]
                        przeciwnik = self.gracze[1 - idx_nadawcy]

                        # A. Obsługa PING (zawsze odpowiadaj obu graczom)
                        if wiad["type"] == MSG_PING:
                            wyslij(s, MSG_PONG, {})
                            continue

                        # B. Obsługa rozłączenia (BYE)
                        if wiad["type"] == MSG_BYE:
                            print(f"[GRA] {nadawca['login']} opuścił grę.")
                            try:
                                wyslij(przeciwnik["sock"], MSG_WIN, {
                                    "winner": przeciwnik["login"],
                                    "reason": "Przeciwnik poddał mecz/rozłączył się"
                                })
                            except: pass
                            return

                        # C. Obsługa Ruchu (MOVE)
                        if wiad["type"] == MSG_MOVE:
                            # Sprawdź czy to tura tego gracza
                            if idx_nadawcy != self.aktywny:
                                wyslij(s, MSG_ERROR, {"msg": "Czekaj na swoją kolej!"})
                                continue

                            payload = wiad.get("payload", {})
                            row, col = payload.get("row"), payload.get("col")

                            # Walidacja danych
                            if not (isinstance(row, int) and isinstance(col, int) and 0 <= row <= 2 and 0 <= col <= 2):
                                wyslij(s, MSG_ERROR, {"msg": "Błędne współrzędne"})
                                
                                continue

                            if self.plansza[row][col] != ".":
                                wyslij(s, MSG_ERROR, {"msg": "To pole jest zajęte"})
                
                                continue

                            # Wykonaj ruch
                            self.plansza[row][col] = nadawca["symbol"]
                            print(f"[GRA] {nadawca['login']} postawił {nadawca['symbol']} na ({row}, {col})")

                            # Wyślij stan planszy do OBU graczy
                            self.wyslij_do_obu(MSG_BOARD, {
                                "board": self.plansza,
                                "last_move": {"row": row, "col": col, "symbol": nadawca["symbol"]}
                            })

                            # Sprawdź wygraną
                            zwyciezca_symbol = self.sprawdz_wygrana()
                            if zwyciezca_symbol:
                                self.wyslij_do_obu(MSG_WIN, {
                                    "winner": nadawca["login"],
                                    "symbol": zwyciezca_symbol
                                })
                                return

                            # Sprawdź remis
                            if self.sprawdz_remis():
                                self.wyslij_do_obu(MSG_DRAW, {"msg": "Koniec ruchów - remis!"})
                                return

                            # Zmiana tury
                            self.aktywny = 1 - self.aktywny
                            wyslij(self.gracze[self.aktywny]["sock"], MSG_YOUR_TURN, {"msg": "Twój ruch!"})

                    except (ConnectionError, ValueError) as e:
                        # Jeśli jeden gracz padnie, drugi wygrywa walkowerem
                        idx_nadawcy = 0 if s == self.gracze[0]["sock"] else 1
                        przeciwnik = self.gracze[1 - idx_nadawcy]
                        print(f"[GRA] Błąd połączenia z {self.gracze[idx_nadawcy]['login']}: {e}")
                        try:
                            wyslij(przeciwnik["sock"], MSG_WIN, {
                                "winner": przeciwnik["login"],
                                "reason": "Utrata połączenia z przeciwnikiem"
                            })
                        except: pass
                        return

def obsluz_klienta(sock: socket.socket, addr):
    """
    Wątek dla każdego nowego klienta.
    Loguje, dodaje do poczekalni, a gdy jest para — startuje grę.
    """
    sock.settimeout(TIMEOUT)

    login = zaloguj_klienta(sock, addr)
    if not login:
        try:
            wyslij(sock, MSG_BYE, {"reason": "Błąd autoryzacji"})
        except Exception:
            pass
        sock.close()
        return

    # Dodaj do poczekalni
    with poczekalnia_lock:
        # Sprawdź czy ten użytkownik nie jest już w poczekalni
        if any(p[1] == login for p in poczekalnia):
            wyslij(sock, MSG_ERROR, {
                "code": 409,
                "msg": "Jesteś już w poczekalni"
            })
            sock.close()
            return

        poczekalnia.append((sock, login))
        pozycja = len(poczekalnia)
        print(f"[SERWER] {login} dołączył do poczekalni ({pozycja} graczy)")

        if len(poczekalnia) >= 2:
            # Mamy parę! Pobierz dwóch graczy z poczekalni
            sock1, login1 = poczekalnia.pop(0)
            sock2, login2 = poczekalnia.pop(0)
        else:
            sock1 = None  # jeszcze nie ma pary

    if sock1 is None:
        # Czekamy na drugiego gracza
        wyslij(sock, MSG_WAIT, {"msg": "Czekam na przeciwnika..."})
        return
    else:
        # Para znaleziona — uruchom grę w nowym wątku
        gra = GraKolkoKrzyzyk(sock1, login1, sock2, login2)
        watek_gry = threading.Thread(target=gra.graj, daemon=True)
        watek_gry.start()


def uruchom_serwer():
    """Główna funkcja serwera."""
    serwer_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Pozwól od razu zajać port po restarcie (bez czekania na TIME_WAIT)
    serwer_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serwer_sock.bind((HOST, PORT))

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain("server.crt", "server.key")

    serwer_sock.listen(10)
    print(f"[SERWER] Działa na {HOST}:{PORT}")
    print(f"[SERWER] Użytkownicy: {list(UZYTKOWNICY.keys())}")

    try:
        while True:
            raw_sock, addr = serwer_sock.accept()
            sock = context.wrap_socket(raw_sock, server_side=True)
            # Każdy klient dostaje swój wątek
            watek = threading.Thread(
                target=obsluz_klienta,
                args=(sock, addr),
                daemon=True
            )
            watek.start()
    except KeyboardInterrupt:
        print("\n[SERWER] Zamykam...")
    finally:
        serwer_sock.close()


if __name__ == "__main__":
    uruchom_serwer()