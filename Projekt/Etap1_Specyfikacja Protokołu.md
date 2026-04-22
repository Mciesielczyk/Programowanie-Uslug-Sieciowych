# Specyfikacja Protokołu TKTP
## TicTacToe Protocol — wersja 1.0

**Przedmiot:** Programowanie Uslug Sieciowych — Projekt grupowy

**Język implementacji:** Python

**Data:** Kwiecień 2026

**Autorzy:**
* Michał Antosiewicz (151401)
* Michał Ciesielczyk (151412)

---

## Spis treści

1. [Cel protokołu i zakres](#1-cel-protokołu-i-zakres)
2. [Założenia techniczne](#2-założenia-techniczne)
3. [Struktura komunikatów](#3-struktura-komunikatów)
4. [Model stanów i przebieg komunikacji](#4-model-stanów-i-przebieg-komunikacji)
5. [Bezpieczeństwo](#5-bezpieczeństwo)
6. [Obsługa błędów i awarii połączenia](#6-obsługa-błędów-i-awarii-połączenia)
7. [Przykładowe scenariusze komunikacji](#7-przykładowe-scenariusze-komunikacji)

---

## 1. Cel protokołu i zakres

### 1.1 Do czego służy protokół?

TKTP (TicTacToe Protocol) to protokół warstwy aplikacyjnej zaprojektowany do obsługi sieciowej gry w kółko i krzyżyk dla dwóch graczy w modelu klient–serwer. Protokół definiuje pełen cykl życia sesji gry: od nawiązania połączenia i uwierzytelnienia, przez wymianę ruchów, aż do zakończenia rozgrywki.

### 1.2 Jakie problemy rozwiązuje?

Protokół rozwiązuje następujące problemy:

- **Synchronizacja stanu gry** — serwer jest jedynym źródłem prawdy o stanie planszy; klienci wysyłają ruchy i otrzymują potwierdzony stan
- **Kolejność ruchów** — protokół jawnie informuje gracza o tym, kiedy jest jego tura (komunikat `YOUR_TURN`)
- **Uwierzytelnienie** — tylko zarejestrowani użytkownicy mogą uczestniczyć w rozgrywce
- **Integralność wiadomości** — każda wiadomość jest podpisana cyfrowo (HMAC-SHA256), co uniemożliwia jej modyfikację w trakcie transmisji
- **Ochrona przed replay attack** — każda wiadomość posiada unikalny identyfikator (UUID) oraz znacznik czasu
- **Obsługa awarii** — protokół definiuje zachowanie przy utracie połączenia, timeoucie i nieprawidłowych pakietach

### 1.3 Model działania

Protokół działa w modelu **klient–serwer**:

- **Serwer** jest centralnym węzłem: przechowuje stan gry, waliduje ruchy, rozstrzyga wynik, zarządza sesjami wielu par graczy jednocześnie
- **Klient** łączy się z serwerem, uwierzytelnia się, dołącza do poczekalni, a następnie uczestniczy w rozgrywce

Klient A i Klient B łączą się przez TCP do centralnego Serwera. Serwer pośredniczy we wszystkich wiadomościach — gracze nie komunikują się ze sobą bezpośrednio. Każda para graczy obsługiwana jest w osobnym wątku serwera.

---

## 2. Założenia techniczne

### 2.1 Transport: TCP

Protokół używa TCP (Transmission Control Protocol) jako warstwy transportowej. Wybór TCP wynika z następujących właściwości:

| Właściwość | Znaczenie dla TKTP |
|---|---|
| Niezawodna dostawa | Wiadomości nie giną bez wykrycia błędu |
| Zachowanie kolejności | Ruchy graczy docierają w właściwej kolejności |
| Kontrola przepływu | Serwer nie jest zalewany danymi |
| Połączeniowość | Wykrycie zerwania połączenia przez zamknięcie socketa |

Port domyślny: **5555**

### 2.2 Kodowanie wiadomości: JSON z binarnym nagłówkiem

Każda wiadomość składa się z dwóch części. Pierwsza to **nagłówek** o stałej długości 4 bajtów, przechowujący długość ciała jako 32-bitową liczbę całkowitą bez znaku w formacie big-endian. Druga to **ciało** o zmiennej długości N bajtów, zawierające dane JSON zakodowane w UTF-8.

- **Nagłówek:** 4 bajty, liczba całkowita bez znaku, big-endian — długość ciała w bajtach
- **Ciało:** JSON zakodowany w UTF-8

Wybór JSON uzasadniony jest czytelnością (ułatwia debugowanie i dokumentowanie), powszechnością i wbudowaną obsługą w Pythonie. Nagłówek binarny jest niezbędny, ponieważ TCP jest strumieniowy — bez jawnej długości nie wiadomo, gdzie kończy się jedna wiadomość, a zaczyna kolejna.

### 2.3 Założenia dotyczące niezawodności

| Poziom | Co zapewnia | Co NIE zapewnia |
|---|---|---|
| TCP | Dostarczenie bajtów, kolejność, wykrycie zerwania | Granice wiadomości, semantykę aplikacyjną |
| TKTP | Granice wiadomości (nagłówek 4B), integralność (HMAC), unikalność (UUID), porządek logiczny sesji | Retransmisję po timeout (sesja jest kończona) |

Protokół TKTP nie implementuje retransmisji na poziomie aplikacyjnym — przy utracie połączenia sesja jest kończona, a drugi gracz otrzymuje wygraną walkowerem. 

---

## 3. Struktura komunikatów

### 3.1 Wspólne pola każdej wiadomości (wymagane)

Każdy komunikat TKTP jest obiektem JSON zawierającym następujące pola:

| Pole | Typ  | Opis |
|---|---|---|
| `type` | string  | Typ wiadomości (np. `"HELLO"`) |
| `msg_id` | string (UUID4)  | Unikalny identyfikator wiadomości |
| `timestamp` | float  | Unix timestamp (sekundy) |
| `payload` | object  | Dane właściwe dla danego typu |
| `hmac` | string (hex)  | Podpis HMAC-SHA256 |

### 3.2 Typy wiadomości

| Typ | Kierunek | Opis |
|---|---|---|
| `HELLO` | C→S, S→C | Inicjacja połączenia / potwierdzenie |
| `AUTH` | C→S | Dane logowania (login + hasło) |
| `AUTH_OK` | S→C | Potwierdzenie pomyślnego logowania |
| `AUTH_ERR` | S→C | Odmowa logowania |
| `WAIT` | S→C | Oczekiwanie na drugiego gracza |
| `START` | S→C | Start gry, przydzielenie symbolu |
| `MOVE` | C→S | Ruch gracza |
| `BOARD` | S→C | Nowy stan planszy po ruchu |
| `YOUR_TURN` | S→C | Informacja o turze gracza |
| `WIN` | S→C | Koniec gry — jest zwycięzca |
| `DRAW` | S→C | Koniec gry — remis |
| `ERROR` | S→C | Błąd (protokołu lub reguł gry) |
| `BYE` | C→S, S→C | Zakończenie sesji |
| `PING` | C→S | Sprawdzenie żywotności połączenia |
| `PONG` | S→C | Odpowiedź na PING |

### 3.3 Pola payload dla każdego typu

#### HELLO (klient → serwer)
```json
{
  "type": "HELLO",
  "msg_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": 1700000000.123,
  "payload": {
    "login": "gracz1"
  },
  "hmac": "a3f5c2..."
}
```

#### HELLO (serwer → klient)
```json
{
  "type": "HELLO",
  "msg_id": "...",
  "timestamp": 1700000000.456,
  "payload": {
    "msg": "Witaj! Podaj dane logowania."
  },
  "hmac": "..."
}
```

#### AUTH (klient → serwer)
```json
{
  "type": "AUTH",
  "msg_id": "...",
  "timestamp": 1700000001.0,
  "payload": {
    "login": "gracz1",
    "password": "haslo1"
  },
  "hmac": "..."
}


#### AUTH_OK / AUTH_ERR (serwer → klient)
```json
{
  "type": "AUTH_OK",
  "payload": { "msg": "Zalogowano jako gracz1" },
  ...
}
```
```json
{
  "type": "AUTH_ERR",
  "payload": {
    "msg": "Błędny login lub hasło",
    "attempts_left": 2
  },
  ...
}
```

#### START (serwer → klient)
```json
{
  "type": "START",
  "payload": {
    "symbol": "X",
    "rywal": "gracz2",
    "zaczynasz": true
  },
  ...
}
```

#### MOVE (klient → serwer)
```json
{
  "type": "MOVE",
  "payload": {
    "row": 1,
    "col": 2
  },
  ...
}
```
Pola wymagane: `row` (int, 0–2), `col` (int, 0–2).

#### BOARD (serwer → klient)
```json
{
  "type": "BOARD",
  "payload": {
    "board": [
      [".", ".", "."],
      [".", "X", "."],
      [".", ".", "."]
    ],
    "last_move": { "row": 1, "col": 1, "symbol": "X" }
  },
  ...
}
```

#### WIN (serwer → klient)
```json
{
  "type": "WIN",
  "payload": {
    "winner": "gracz1",
    "symbol": "X",
    "reason": ""
  },
  ...
}
```
Pole `reason` jest opcjonalne — wypełniane przy wygranej walkowerem (np. `"Przeciwnik przekroczył czas"`).

#### ERROR (serwer → klient)
```json
{
  "type": "ERROR",
  "payload": {
    "code": 422,
    "msg": "Pole row i col muszą być liczbami całkowitymi"
  },
  ...
}
```

#### BYE (obie strony)
```json
{
  "type": "BYE",
  "payload": {
    "reason": "Dziękujemy za grę!"
  },
  ...
}
```

#### PING / PONG
```json
{ "type": "PING", "payload": {}, ... }
{ "type": "PONG", "payload": {}, ... }
```

### 3.4 Walidacja — co jest błędem formatu

Następujące sytuacje skutkują odpowiedzią `ERROR` lub zamknięciem połączenia:

| Błąd | Kod | Działanie |
|---|---|---|
| Brak wymaganego pola (`type`, `msg_id`, `hmac`) | 400 | ERROR + zamknięcie |
| Nieprawidłowy JSON | 400 | Zamknięcie połączenia |
| Błędny HMAC | 401 | Zamknięcie połączenia |
| Nieznany typ wiadomości | 400 | ERROR |
| Wiadomość > 1 MB | 413 | Zamknięcie połączenia |
| `row`/`col` poza zakresem 0–2 | 422 | ERROR (tura pozostaje przy graczu) |
| Ruch na zajęte pole | 409 | ERROR (tura pozostaje przy graczu) |
| Ruch gdy nie jest tura gracza | 403 | ERROR |

---

## 4. Model stanów i przebieg komunikacji

### 4.1 Stany po stronie klienta

Klient przechodzi przez następujące stany w trakcie sesji:

1. **ROZŁĄCZONY** — stan początkowy, brak aktywnego połączenia TCP.
2. **POŁĄCZONY** — TCP nawiązany, klient czeka na wymianę HELLO. Błąd TCP cofa do stanu ROZŁĄCZONY.
3. **HANDSHAKE** — klient wysłał HELLO i oczekuje na HELLO od serwera, następnie przesyła AUTH.
4. **ZALOGOWANY** — serwer potwierdził AUTH_OK. Klient trafia do poczekalni i czeka na wiadomość START (opcjonalnie poprzedzoną WAIT).
5. **W_GRZE** — gra aktywna. Klient naprzemiennie odbiera YOUR_TURN i wysyła MOVE, po każdym ruchu otrzymuje BOARD. Stan trwa do odebrania WIN lub DRAW.
6. **KONIEC_GRY** — gra zakończona. Obie strony wymieniają BYE i zamykają połączenie.

### 4.2 Stany po stronie serwera (na sesję)

Serwer prowadzi osobny stan dla każdej sesji klienckiej:

1. **OCZEKUJE_HELLO** — nowe połączenie TCP przyjęte, serwer czeka na pierwsze HELLO od klienta.
2. **OCZEKUJE_AUTH** — serwer odpowiedział HELLO, czeka na wiadomość AUTH. Przy błędnych danych wysyła AUTH_ERR i wraca do oczekiwania na kolejne AUTH. Po 3 nieudanych próbach przechodzi do zamknięcia sesji.
3. **POCZEKALNIA** — klient zalogowany, umieszczony w kolejce oczekujących. Gdy w poczekalni pojawią się dwie osoby, serwer tworzy nową sesję gry i przechodzi do następnego stanu.
4. **GRA_AKTYWNA** — serwer przyjmuje MOVE od gracza, którego jest tura, waliduje ruch, aktualizuje planszę i rozsyła BOARD do obu graczy. Błędne ruchy skutkują ERROR bez zmiany tury. Stan trwa do wykrycia wygranej lub remisu.
5. **GRA_ZAKONCZONA** — serwer wysyła WIN lub DRAW do obu graczy, a następnie BYE. Sesja zostaje zamknięta.

### 4.3 Przebieg komunikacji — poprawna sesja

Poniżej opisano kolejność wiadomości w trakcie typowej sesji z udziałem dwóch klientów.

**Faza logowania Klienta A:** Klient A wysyła HELLO, serwer odpowiada HELLO. Klient wysyła AUTH, serwer odpowiada AUTH_OK. Ponieważ Klient B jeszcze nie dołączył, serwer wysyła WAIT.

**Faza logowania Klienta B:** Analogicznie — HELLO, HELLO, AUTH, AUTH_OK. W momencie gdy Klient B trafia do poczekalni, serwer ma parę i natychmiast uruchamia grę.

**Start gry:** Serwer wysyła START do Klienta A (symbol X, zaczynasz: true) oraz START do Klienta B (symbol O, zaczynasz: false). Następnie wysyła YOUR_TURN do Klienta A.

**Wymiana ruchów (powtarza się naprzemiennie):** Aktywny gracz wysyła MOVE z polami row i col. Serwer waliduje ruch, aktualizuje planszę i wysyła BOARD do obu graczy. Jeśli gra trwa, serwer wysyła YOUR_TURN do drugiego gracza.

**Zakończenie:** Po ruchu wygrywającym serwer wysyła WIN do obu graczy (lub DRAW przy remisie), a następnie BYE do obu. Oba połączenia TCP są zamykane.

### 4.4 Zasady timeoutów, keep-alive i retry

| Mechanizm | Wartość | Opis |
|---|---|---|
| **Timeout połączenia** | 30 s | Jeśli żadna wiadomość nie nadejdzie przez 30 s, serwer uznaje klienta za rozłączonego |
| **PING interval** | 10 s | Klient wysyła `PING` co 10 sekund gdy trwa gra |
| **PONG timeout** | 30 s | Brak PONG w ciągu 30 s = rozłączenie |
| **Maks. próby AUTH** | 3 | Po 3 nieudanych próbach logowania połączenie jest zamykane |
| **Retry** | brak | Protokół nie implementuje retransmisji — przy utracie sesji gra się kończy |

Brak retransmisji jest celowym uproszczeniem: TCP gwarantuje dostarczenie bajtów, więc jedynym scenariuszem wymagającym retry jest całkowita utrata połączenia. W takim przypadku kontynuacja gry nie ma sensu (gracz i tak musiałby się zalogować ponownie).

---

## 5. Bezpieczeństwo

### 5.1 Poufność

W aktualnej wersji aplikacji dane są przesyłane dzięki zastosowaniu SSL/TLS (Secure Sockets Layer / Transport Layer Security). Cała komunikacja TCP jest opakowana w szyfrowany tunel przed wysłaniem jakichkolwiek danych aplikacyjnych.

- Szyfrowanie: Wykorzystanie ssl.SSLContext gwarantuje, że dane (w tym hasła i loginy) są nieczytelne dla osób trzecich podsłuchujących ruch sieciowy.

- Certyfikacja: Serwer wykorzystuje parę kluczy (server.crt, server.key). W obecnej fazie projektowej (środowisko deweloperskie) używane są certyfikaty samopodpisane, a klient operuje w trybie CERT_NONE, co zapewnia szyfrowanie, ale pomija weryfikację wystawcy.

### 5.2 Integralność — HMAC-SHA256

Każda wiadomość jest podpisana za pomocą HMAC-SHA256. Podpis jest obliczany na podstawie:

```
HMAC = SHA256(SECRET_KEY, msg_id || JSON(payload, sort_keys=True))
```

Gdzie `||` oznacza konkatenację. Użycie `sort_keys=True` gwarantuje deterministyczną reprezentację JSON niezależnie od kolejności pól.

Dzięki temu:
- Odbiorca może wykryć każdą modyfikację treści wiadomości
- Atakujący bez znajomości klucza nie może wygenerować poprawnego HMAC

Weryfikacja używa `hmac.compare_digest()` zamiast zwykłego porównania stringów, co chroni przed **timing attack** (atakujący mierzący czas odpowiedzi mógłby odgadnąć HMAC bajt po bajcie).


### 5.3 Uwierzytelnienie

Uwierzytelnienie odbywa się w fazie `HANDSHAKE` przed dopuszczeniem gracza do poczekalni:

1. Klient wysyła `HELLO` z loginem
2. Serwer odpowiada `HELLO`
3. Klient wysyła `AUTH` z loginem i hasłem zabezpieczone TLS
4. Serwer weryfikuje: `SHA256(hasło) == hash_w_bazie`
5. Maksymalnie 3 próby, po czym połączenie jest zamykane

**Przechowywanie haseł:** Serwer przechowuje hashe SHA-256 haseł, nigdy plaintext. 

### 5.4 Autoryzacja

Protokół implementuje prostą autoryzację:
- Tylko zalogowani użytkownicy mogą dołączyć do poczekalni
- Tylko gracz, którego jest tura, może wysłać `MOVE` (serwer odrzuca ruchy poza kolejnością z kodem 403)
- Jeden użytkownik nie może dołączyć do poczekalni dwukrotnie

### 5.5 Ochrona przed replay attack

Każda wiadomość zawiera:
- `msg_id` — UUID4, unikalny na całe życie aplikacji (prawdopodobieństwo kolizji ≈ 0)
- `timestamp` — Unix timestamp

Dzięki UUID4 ponowne wysłanie przechwyconych pakietów daje wiadomości ze starym `msg_id`. Serwer może opcjonalnie odrzucać wiadomości z `msg_id` już widzianym w bieżącej sesji lub z `timestamp` starszym niż N sekund.

### 5.6 Model zagrożeń

| Zagrożenie | Wektor | Ochrona w TKTP |
|---|---|---|
| Podsłuch (eavesdropping) | Sieć lokalna/publiczna |  Szyfrowanie TLS |
| Modyfikacja pakietów (MITM) | Pośrednik sieciowy | HMAC-SHA256 — wykrycie modyfikacji |
| Replay attack | Ponowne wysłanie pakietu |  UUID msg_id + timestamp |
| Timing attack na HMAC | Pomiar czasu weryfikacji |  `hmac.compare_digest()` |
| Brute-force haseł | Wiele prób logowania |  Limit 3 prób, zamknięcie połączenia |
| Flood/DoS | Duże pakiety |  Limit 1 MB na wiadomość |
| Nieautoryzowany ruch | Gra poza kolejnością |  Serwer weryfikuje turę |
| Podszywanie się pod gracza | Fałszywy klient |  Certyfikaty SSL |

---

## 6. Obsługa błędów i awarii połączenia

### 6.1 Kody błędów

| Kod | Nazwa | Znaczenie |
|---|---|---|
| 400 | BAD_REQUEST | Nieprawidłowy format wiadomości, brak wymaganego pola, nieznany typ |
| 401 | UNAUTHORIZED | Błędny HMAC — wiadomość odrzucona |
| 403 | FORBIDDEN | Akcja niedozwolona (ruch poza kolejnością, podwójne logowanie) |
| 409 | CONFLICT | Pole na planszy jest już zajęte; użytkownik już w poczekalni |
| 413 | TOO_LARGE | Wiadomość przekracza 1 MB |
| 422 | UNPROCESSABLE | Nieprawidłowe dane (np. `row=5`, `col="abc"`) |
| 500 | SERVER_ERROR | Wewnętrzny błąd serwera |

### 6.2 Zachowanie po błędach składni/protokołu

- **Błędny JSON:** serwer zamyka połączenie bez wysyłania odpowiedzi (nie można zbudować poprawnej odpowiedzi)
- **Błędny HMAC:** serwer zamyka połączenie (potencjalny atak)
- **Nieznany typ wiadomości:** serwer wysyła `ERROR(400)` i kontynuuje sesję
- **Błąd walidacji ruchu** (kod 409, 422): serwer wysyła `ERROR` i ponownie wysyła `YOUR_TURN` — gracz może spróbować ponownie

### 6.3 Timeout połączenia

Jeśli od ostatniej odebranej wiadomości minęło więcej niż 30 sekund, serwer wysyła do tego klienta BYE z powodem "Timeout", a drugiemu graczowi wysyła WIN z powodem "Przeciwnik przekroczył czas". Następnie oba sockety są zamykane.

Klient zapobiega timeout poprzez wysyłanie `PING` co 10 sekund gdy trwa gra. Serwer odpowiada `PONG`.

### 6.4 Utrata połączenia w trakcie sesji

Gdy TCP wykryje zerwanie połączenia (socket rzuca wyjątek przy `recv` lub `send`), serwer identyfikuje którego gracza dotyczy błąd, wysyła drugiemu graczowi WIN z powodem "Utrata połączenia z przeciwnikiem", zamyka oba sockety i kończy wątek gry.

### 6.5 Duplikaty i niekompletne wiadomości

**Niekompletne wiadomości:** Funkcja `_odbierz_dokladnie(sock, n)` pętluje `recv()` do uzyskania dokładnie `n` bajtów. TCP może podzielić wiadomość na wiele segmentów — ta funkcja to obsługuje.

**Duplikaty na poziomie aplikacyjnym:** Każda wiadomość ma unikalny `msg_id` (UUID4). Serwer może opcjonalnie prowadzić zbiór widzianych `msg_id` w bieżącej sesji i odrzucać duplikaty. W wersji 1.0 duplikaty są wykrywane przez `timestamp` — wiadomość starsza niż 60 sekund jest podejrzana.

### 6.6 Limity i ochrona przed nadużyciami

| Limit | Wartość | Działanie po przekroczeniu |
|---|---|---|
| Rozmiar wiadomości | 1 MB | Zamknięcie połączenia (kod 413) |
| Próby logowania | 3 | Zamknięcie połączenia |
| Timeout bez aktywności | 30 s | BYE + zamknięcie |
| Jeden użytkownik w poczekalni | 1 instancja | ERROR(409) + zamknięcie |

---

## 7. Przykładowe scenariusze komunikacji

### Scenariusz 1: Poprawna sesja — zakończona wygraną

Poniżej pełna sekwencja dla jednego klienta (Klient A — symbol X, wygrywa):

```
→ HELLO
  payload: { "login": "gracz1" }

← HELLO
  payload: { "msg": "Witaj! Podaj dane logowania." }

→ AUTH
  payload: { "login": "gracz1", "password": "haslo1" }

← AUTH_OK
  payload: { "msg": "Zalogowano jako gracz1" }

← WAIT
  payload: { "msg": "Czekam na przeciwnika..." }

← START
  payload: { "symbol": "X", "rywal": "gracz2", "zaczynasz": true }

← YOUR_TURN
  payload: { "msg": "Twój ruch!" }

→ MOVE
  payload: { "row": 1, "col": 1 }      ← środek planszy

← BOARD
  payload: {
    "board": [[".",".","."],[".","X","."],[".",".","."]] ,
    "last_move": { "row": 1, "col": 1, "symbol": "X" }
  }

  ... (kilka ruchów obu graczy) ...

← YOUR_TURN
← MOVE { "row": 0, "col": 0 }          ← ruch wygrywający
← BOARD { "board": [["X","X","X"], ...] }

← WIN
  payload: { "winner": "gracz1", "symbol": "X" }

← BYE
  payload: { "msg": "Dziękujemy za grę!" }
```

---

### Scenariusz 2: Błędne logowanie + timeout

```
→ HELLO
  payload: { "login": "gracz1" }

← HELLO
  payload: { "msg": "Witaj! Podaj dane logowania." }

→ AUTH
  payload: { "login": "gracz1", "password": "bledne_haslo" }

← AUTH_ERR
  payload: { "msg": "Błędny login lub hasło", "attempts_left": 2 }

→ AUTH
  payload: { "login": "gracz1", "password": "znowu_zle" }

← AUTH_ERR
  payload: { "msg": "Błędny login lub hasło", "attempts_left": 1 }

→ AUTH
  payload: { "login": "gracz1", "password": "ostatnia_proba" }

← AUTH_ERR
  payload: { "msg": "Błędny login lub hasło", "attempts_left": 0 }

← BYE
  payload: { "reason": "Błąd autoryzacji" }

  [połączenie zamknięte]
```

---

### Scenariusz 3: Nieprawidłowy ruch + rozłączenie przeciwnika

```
  ... (po poprawnym logowaniu i START) ...

← YOUR_TURN

→ MOVE
  payload: { "row": 5, "col": 0 }        ← poza planszą!

← ERROR
  payload: { "code": 422, "msg": "Ruch poza planszą (0-2)" }

← YOUR_TURN                               ← serwer daje szansę ponownie

→ MOVE
  payload: { "row": 1, "col": 1 }        ← zajęte!

← ERROR
  payload: { "code": 409, "msg": "To pole jest już zajęte" }

← YOUR_TURN

→ MOVE
  payload: { "row": 0, "col": 0 }        ← poprawny ruch

← BOARD
  payload: { "board": [...], "last_move": {...} }

  ... (tura przechodzi do gracza B) ...

  [GRACZ B TRACI POŁĄCZENIE — TCP exception po stronie serwera]

← WIN
  payload: {
    "winner": "gracz1",
    "symbol": "X",
    "reason": "Utrata połączenia z przeciwnikiem"
  }

← BYE
  payload: { "msg": "Dziękujemy za grę!" }
```

---

### Scenariusz 4: Próba sfałszowania wiadomości (wykrycie błędnego HMAC)

```
  [Atakujący przechwytuje pakiet MOVE i zmienia row z 1 na 0]

→ MOVE (zmodyfikowany)
  payload:  { "row": 0, "col": 1 }   ← zmienione przez atakującego
  hmac:     "a3f5c2..."               ← HMAC wciąż dla row=1, col=1

  [Serwer oblicza HMAC dla odebranego payload — wartości się nie zgadzają]

  [Serwer zamyka połączenie bez wysyłania odpowiedzi]
  [Drugiemu graczowi: WIN z powodem "Utrata połączenia z przeciwnikiem"]
```

---

*Koniec specyfikacji protokołu TKTP*