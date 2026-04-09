import asyncio

from aioquic.asyncio import serve, QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import StreamDataReceived
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.x509 import load_pem_x509_certificate

# Definiujemy protokół obsługujący zdarzenia
class MyQuicHandler(QuicConnectionProtocol):
    def quic_event_received(self, event):
        if isinstance(event, StreamDataReceived):
            data = event.data.decode()
            print(f"[*] QUIC Odebrano: {data}")
            
            # Odpowiedź
            response = f"Serwer QUIC potwierdza: {data}".encode()
            self._quic.send_stream_data(event.stream_id, response, end_stream=True)
            self.transmit() # Wysłanie danych do klienta

async def main():
    with open("server.crt", "rb") as f:
        cert = load_pem_x509_certificate(f.read())
    with open("server.key", "rb") as f:
        key = load_pem_private_key(f.read(), password=None)

    configuration = QuicConfiguration(is_client=False)
    configuration.certificate = cert
    configuration.private_key = key

    print("[*] Serwer QUIC (UDP 4433) startuje...")
    await serve(
        host="0.0.0.0",
        port=4433,
        configuration=configuration,
        create_protocol=MyQuicHandler,
    )
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[*] Serwer zatrzymany.")