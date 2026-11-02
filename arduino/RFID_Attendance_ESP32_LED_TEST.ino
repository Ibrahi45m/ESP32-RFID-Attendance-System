
#include <SPI.h>
#include <MFRC522.h>
#include <string.h>

#define SS_PIN 5
#define RST_PIN 22

MFRC522 rfid(SS_PIN, RST_PIN);

// Simulation des LEDs via Serial
char commande[24];
size_t positionCommande = 0;

// ====================================
// Reception des commandes de Python
// ====================================
void verifierFeedbackPC() {

  while (Serial.available() > 0) {

    char c = (char)Serial.read();

    if (c == '\r') {
      continue;
    }

    if (c == '\n') {

      commande[positionCommande] = '\0';

      if (strcmp(commande, "LED:GREEN") == 0) {
        Serial.println("LED_SIM:GREEN");
      }

      else if (strcmp(commande, "LED:WHITE") == 0) {
        Serial.println("LED_SIM:WHITE");
      }

      positionCommande = 0;
    }

    else if (positionCommande < sizeof(commande) - 1) {
      commande[positionCommande++] = c;
    }

    else {
      // Commande trop longue : vider le buffer
      positionCommande = 0;
    }
  }
}

// ====================================
// Initialisation
// ====================================
void setup() {

  Serial.begin(115200);

  SPI.begin(18, 19, 23, 5);
  rfid.PCD_Init();

  delay(200);

  Serial.println("=== RFID ATTENDANCE SYSTEM ===");
  Serial.println("Mode RFID + LED Simulation");
  Serial.println("Approchez votre carte RFID...");
}

// ====================================
// Boucle principale
// ====================================
void loop() {

  // 1. Ecouter Python en permanence
  verifierFeedbackPC();

  // 2. Detecter une nouvelle carte
  if (!rfid.PICC_IsNewCardPresent()) {
    return;
  }

  // 3. Lire le UID
  if (!rfid.PICC_ReadCardSerial()) {
    return;
  }

  // 4. Convertir UID en texte
  String uidText = "";

  for (byte i = 0; i < rfid.uid.size; i++) {

    if (rfid.uid.uidByte[i] < 0x10) {
      uidText += "0";
    }

    uidText += String(rfid.uid.uidByte[i], HEX);

    if (i < rfid.uid.size - 1) {
      uidText += " ";
    }
  }

  uidText.toUpperCase();

  // 5. Envoyer UID a Python
  Serial.print("Card UID: ");
  Serial.println(uidText);

  // Python valide ensuite la presence
  // et renvoie LED:GREEN ou LED:WHITE

  // 6. Terminer la lecture RFID
  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
}
