
#include <SPI.h>
#include <MFRC522.h>
#include <string.h>

#define SS_PIN 5
#define RST_PIN 22

#define LED_GREEN 25
#define LED_RED 26

#define LED_DURATION 800

MFRC522 rfid(SS_PIN, RST_PIN);

char commande[24];
size_t positionCommande = 0;

unsigned long debutLED = 0;
bool ledActive = false;

// ====================================
// Gestion des LEDs
// ====================================
void eteindreLEDs() {
  digitalWrite(LED_GREEN, LOW);
  digitalWrite(LED_RED, LOW);
  ledActive = false;
}

void activerLED(int pin) {
  eteindreLEDs();

  digitalWrite(pin, HIGH);
  debutLED = millis();
  ledActive = true;
}

void verifierDureeLED() {
  if (ledActive &&
      millis() - debutLED >= LED_DURATION) {
    eteindreLEDs();
  }
}

// ====================================
// Reception des commandes Python
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

        activerLED(LED_GREEN);
        Serial.println("LED_SIM:GREEN");

      } else if (
        strcmp(commande, "LED:WHITE") == 0 ||
        strcmp(commande, "LED:RED") == 0
      ) {

        activerLED(LED_RED);
        Serial.println("LED_SIM:WHITE");

      }

      positionCommande = 0;
    }

    else if (positionCommande <
             sizeof(commande) - 1) {

      commande[positionCommande++] = c;

    } else {

      positionCommande = 0;
    }
  }
}

// ====================================
// Initialisation
// ====================================
void setup() {

  Serial.begin(115200);

  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_RED, OUTPUT);

  eteindreLEDs();

  SPI.begin(18, 19, 23, 5);
  rfid.PCD_Init();

  delay(200);

  Serial.println("=== RFID ATTENDANCE SYSTEM ===");
  Serial.println("Mode RFID + LED Physique");
  Serial.println("Approchez votre carte RFID...");
}

// ====================================
// Boucle principale
// ====================================
void loop() {

  verifierFeedbackPC();
  verifierDureeLED();

  if (!rfid.PICC_IsNewCardPresent()) {
    return;
  }

  if (!rfid.PICC_ReadCardSerial()) {
    return;
  }

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

  Serial.print("Card UID: ");
  Serial.println(uidText);

  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
}
