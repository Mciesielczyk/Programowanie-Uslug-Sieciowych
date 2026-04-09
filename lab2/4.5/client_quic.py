import asyncio

from aioquic.asyncio.client import connect
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import StreamDataReceived

# Tworzymy własną klasę klienta, żeby obsłużyć nadejście danych
class MyClientProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.response_future = asyncio.Future()

    def quic_event_received(self, event):
        if isinstance(event, StreamDataReceived):
            # Gdy przyjdą dane, ustawiamy wynik w naszym Future
            self.response_future.set_result(event.data)

async def run():
    configuration = QuicConfiguration(
    is_client=True,
    server_name="localhost",
    cafile="myCA.pem"       # ← bezpośrednio w konstruktorze
)
    
    # Używamy naszej klasy MyClientProtocol przy łączeniu
    async with connect(
        "localhost", 
        4433, 
        configuration=configuration, 
        create_protocol=MyClientProtocol
    ) as client:
        
        # Pobieramy ID strumienia
        stream_id = client._quic.get_next_available_stream_id()
        print(f"[*] Połączono przez QUIC! Wysyłam dane na strumieniu {stream_id}...")
        
        # Wysyłamy dane
        client._quic.send_stream_data(stream_id, b"Czesc, to ja - szybki klient QUIC!", end_stream=True)
        client.transmit()
        
        # Czekamy na dane używając naszego Future
        print("[*] Czekam na odpowiedź z serwera...")
        response = await client.response_future
        print(f"[*] Odpowiedź serwera: {response.decode()}")

if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass