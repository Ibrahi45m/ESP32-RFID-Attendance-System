"""Lecture ponctuelle UID ESP32/RC522 via port série."""
import os
import time


def lire_uid(timeout_secondes=12, port=None):
    try:
        import serial
    except ImportError as exc:
        raise RuntimeError("PySerial manquant : python -m pip install pyserial") from exc

    port = port or os.getenv("RFID_PORT", "COM7")
    with serial.Serial(port, 115200, timeout=1) as esp32:
        time.sleep(2)  # Redémarrage habituel de l'ESP32 à l'ouverture du port.
        debut = time.monotonic()
        while time.monotonic() - debut < timeout_secondes:
            message = esp32.readline().decode("utf-8", errors="replace").strip()
            if message.startswith("Card UID:"):
                return " ".join(message.split(":", 1)[1].upper().split())
    return None
