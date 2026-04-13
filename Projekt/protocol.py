"""
protocol.py — wspólny moduł protokołu dla kółko i krzyżyk
=========================================================
Odpowiada za:
  - format wiadomości (JSON)
  - podpisywanie wiadomości (HMAC-SHA256) — żeby nikt nie sfałszował pakietu
  - wysyłanie i odbieranie przez socket
  - obsługę błędów i timeoutów

Format każdej wiadomości (bajty w sieci):
  [4 bajty: długość JSON] [N bajtów: JSON]

Przykład JSON:
  {
    "type": "MOVE",
    "msg_id": "abc123",
    "payload": {"row": 1, "col": 2},
    "hmac": "deadbeef..."
  }
"""

import json
import hmac
import hashlib
import struct
import socket
import uuid
import time

# Sekretny klucz wspólny dla klienta i serwera (w prawdziwej apce wysyłany przez TLS)
# W naszej implementacji jest zakodowany na stałe — w dokumentacji zaznaczymy że
# w produkcji byłby wymieniany podczas handshake po TLS
SECRET_KEY = b"super_tajny_klucz_projektu_2025"

# Timeout w sekundach — ile czekamy na dane zanim uznamy że połączenie padło
TIMEOUT = 30

# Typy wiadomości w protokole
MSG_HELLO   = "HELLO"    # powitanie klienta
MSG_AUTH    = "AUTH"     # logowanie (login + hasło)
MSG_AUTH_OK = "AUTH_OK"  # serwer potwierdza logowanie
MSG_AUTH_ERR= "AUTH_ERR" # serwer odrzuca logowanie
MSG_WAIT    = "WAIT"     # czekaj na drugiego gracza
MSG_START   = "START"    # gra się zaczyna, masz symbol X lub O
MSG_MOVE    = "MOVE"     # ruch gracza (row, col)
MSG_BOARD   = "BOARD"    # serwer wysyła stan planszy po ruchu
MSG_YOUR_TURN = "YOUR_TURN"  # twoja kolej
MSG_WIN     = "WIN"      # ktoś wygrał
MSG_DRAW    = "DRAW"     # remis
MSG_ERROR   = "ERROR"    # błąd protokołu / nieprawidłowy ruch
MSG_BYE     = "BYE"      # rozłączenie
MSG_PING    = "PING"     # sprawdzenie czy połączenie żyje
MSG_PONG    = "PONG"     # odpowiedź na ping


def podpisz(payload_dict: dict, msg_id: str) -> str:
    """
    Oblicza HMAC-SHA256 dla wiadomości.
    Podpisujemy: msg_id + posortowany JSON payload
    Dzięki temu nikt nie może zmodyfikować wiadomości bez znajomości klucza.
    """
    dane = msg_id + json.dumps(payload_dict, sort_keys=True)
    return hmac.new(SECRET_KEY, dane.encode(), hashlib.sha256).hexdigest()


def weryfikuj(wiadomosc: dict) -> bool:
    """
    Sprawdza czy HMAC w wiadomości się zgadza.
    Zwraca True jeśli wiadomość jest autentyczna, False jeśli ktoś ją zmienił.
    """
    otrzymany_hmac = wiadomosc.get("hmac", "")
    payload = wiadomosc.get("payload", {})
    msg_id = wiadomosc.get("msg_id", "")
    oczekiwany_hmac = podpisz(payload, msg_id)
    # Używamy compare_digest żeby uniknąć timing attack
    return hmac.compare_digest(otrzymany_hmac, oczekiwany_hmac)


def zbuduj_wiadomosc(typ: str, payload: dict = None) -> dict:
    """
    Tworzy słownik wiadomości gotowy do wysłania.
    Automatycznie dodaje unikalny msg_id i HMAC.
    """
    if payload is None:
        payload = {}
    msg_id = str(uuid.uuid4())  # unikalny ID — chroni przed replay attack
    return {
        "type": typ,
        "msg_id": msg_id,
        "timestamp": time.time(),  # znacznik czasu
        "payload": payload,
        "hmac": podpisz(payload, msg_id)
    }


def wyslij(sock: socket.socket, typ: str, payload: dict = None):
    """
    Buduje wiadomość i wysyła ją przez socket.
    Najpierw wysyła 4 bajty z długością, potem JSON.
    Rzuca ConnectionError jeśli socket padł.
    """
    wiadomosc = zbuduj_wiadomosc(typ, payload)
    dane = json.dumps(wiadomosc).encode("utf-8")
    # struct.pack ">I" = 4 bajty big-endian unsigned int (długość)
    naglowek = struct.pack(">I", len(dane))
    try:
        sock.sendall(naglowek + dane)
    except (BrokenPipeError, OSError) as e:
        raise ConnectionError(f"Błąd wysyłania: {e}")


def odbierz(sock: socket.socket) -> dict:
    """
    Odbiera jedną wiadomość z socketa.
    Czyta 4 bajty nagłówka, potem dokładnie tyle bajtów ile powiedziano.
    Weryfikuje HMAC — jeśli nie pasuje, rzuca ValueError.
    Rzuca ConnectionError jeśli połączenie padło.
    Rzuca TimeoutError jeśli timeout.
    """
    try:
        # Odbierz nagłówek (4 bajty = długość wiadomości)
        naglowek = _odbierz_dokladnie(sock, 4)
        if not naglowek:
            raise ConnectionError("Połączenie zamknięte przez drugą stronę")
        dlugosc = struct.unpack(">I", naglowek)[0]

        # Zabezpieczenie: nie przyjmujemy wiadomości > 1MB
        if dlugosc > 1_000_000:
            raise ValueError(f"Wiadomość za duża: {dlugosc} bajtów")

        # Odbierz właściwą wiadomość
        dane = _odbierz_dokladnie(sock, dlugosc)
        if not dane:
            raise ConnectionError("Połączenie zamknięte w trakcie odbioru")

        wiadomosc = json.loads(dane.decode("utf-8"))

        # Sprawdź HMAC
        if not weryfikuj(wiadomosc):
            raise ValueError("Błędny HMAC — wiadomość mogła zostać zmodyfikowana!")

        return wiadomosc

    except socket.timeout:
        raise TimeoutError("Timeout — brak odpowiedzi")
    except json.JSONDecodeError as e:
        raise ValueError(f"Błędny format JSON: {e}")


def _odbierz_dokladnie(sock: socket.socket, ile: int) -> bytes:
    """
    Pomocnicza funkcja: odbiera dokładnie `ile` bajtów.
    Socket może zwrócić mniej bajtów niż prosimy — ta funkcja pętluje do skutku.
    """
    bufor = b""
    while len(bufor) < ile:
        fragment = sock.recv(ile - len(bufor))
        if not fragment:
            return b""  # połączenie zamknięte
        bufor += fragment
    return bufor