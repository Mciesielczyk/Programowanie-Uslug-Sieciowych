"""
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
from enum import Enum

# Sekretny klucz wspólny dla klienta i serwera
SECRET_KEY = b"super_tajny_klucz_projektu_2025"

# Timeout w sekundach — ile czekamy na dane zanim uznamy że połączenie padło
TIMEOUT = 30

# Typy wiadomości w protokole
class MsgType(str, Enum):
    HELLO      = "HELLO"      # powitanie
    AUTH       = "AUTH"       # logowanie
    AUTH_OK    = "AUTH_OK"    # sukces logowania
    AUTH_ERR   = "AUTH_ERR"   # błąd logowania
    WAIT       = "WAIT"       # poczekalnia
    START      = "START"      # start gry
    MOVE       = "MOVE"       # ruch
    BOARD      = "BOARD"      # stan planszy
    YOUR_TURN  = "YOUR_TURN"  # tura gracza
    WIN        = "WIN"        # wygrana
    DRAW       = "DRAW"       # remis
    ERROR      = "ERROR"      # błąd
    BYE        = "BYE"        # rozłączenie
    PING       = "PING"       # keep-alive
    PONG       = "PONG"       # odpowiedź ping


# szyfrowanie HMAC
def podpisz(payload_dict: dict, msg_id: str) -> str:
    dane = msg_id + json.dumps(payload_dict, sort_keys=True)
    return hmac.new(SECRET_KEY, dane.encode(), hashlib.sha256).hexdigest()

# SPRAWDZANIE HMAC
def weryfikuj(wiadomosc: dict) -> bool:
    otrzymany_hmac = wiadomosc.get("hmac", "")
    payload = wiadomosc.get("payload", {})
    msg_id = wiadomosc.get("msg_id", "")
    oczekiwany_hmac = podpisz(payload, msg_id)
    # Używamy compare_digest żeby uniknąć timing attack
    return hmac.compare_digest(otrzymany_hmac, oczekiwany_hmac)


def zbuduj_wiadomosc(typ: MsgType, payload: dict = None) -> dict:
    if payload is None:
        payload = {}
    msg_id = str(uuid.uuid4())
    return {
        "type": typ.value,  # .value wyciąga czysty string np. "HELLO"
        "msg_id": msg_id,
        "timestamp": time.time(),
        "payload": payload,
        "hmac": podpisz(payload, msg_id)
    }


def wyslij(sock: socket.socket, typ: MsgType, payload: dict = None):
    wiadomosc = zbuduj_wiadomosc(typ, payload)
    dane = json.dumps(wiadomosc).encode("utf-8")
    naglowek = struct.pack(">I", len(dane))
    try:
        sock.sendall(naglowek + dane)
    except (BrokenPipeError, OSError) as e:
        raise ConnectionError(f"Błąd wysyłania: {e}")


#Odbiera jedną wiadomość z socketa
#Czyta 4 bajty nagłówka, potem dokładnie tyle bajtów ile powiedziano
#Weryfikuje HMAC — jeśli nie pasuje, rzuca ValueError
#Rzuca ConnectionError jeśli połączenie padło
#Rzuca TimeoutError jeśli timeout
def odbierz(sock: socket.socket) -> dict:
    try:
        # Odbierz nagłówek 4 bajty
        naglowek = _odbierz_dokladnie(sock, 4)
        if not naglowek:
            raise ConnectionError("Połączenie zamknięte przez drugą stronę")
        dlugosc = struct.unpack(">I", naglowek)[0]

        # nie przyjmujem wiadomości > 1MB
        if dlugosc > 1_000_000:
            raise ValueError(f"Wiadomość za duża: {dlugosc} bajtów")

        # Odbierz właściwą wiadomość
        dane = _odbierz_dokladnie(sock, dlugosc)
        if not dane:
            raise ConnectionError("Połączenie zamknięte w trakcie odbioru")

        wiadomosc = json.loads(dane.decode("utf-8"))

        # Sprawdź HMAC
        if not weryfikuj(wiadomosc):
            print(f"[ALARM] Błędny HMAC od gniazda!")
            sock.close()
            raise ValueError("Błędny HMAC — wiadomość mogła zostać zmodyfikowana!")

        return wiadomosc

    except socket.timeout:
        raise TimeoutError("Timeout — brak odpowiedzi")
    except json.JSONDecodeError as e:
        raise ValueError(f"Błędny format JSON: {e}")


# Funkcja pomocnicza do odbierania dokładnie ile bajtów z socketa
def _odbierz_dokladnie(sock: socket.socket, ile: int) -> bytes:
    
    bufor = b""
    while len(bufor) < ile:
        fragment = sock.recv(ile - len(bufor))
        if not fragment:
            return b""  # połączenie zamknięte
        bufor += fragment
    return bufor