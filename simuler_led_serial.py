"""Simulation sans materiel, sans ouvrir COM7 et sans toucher attendance.db."""
from rfid_led_feedback import couleur_pour_statut, envoyer_feedback


class PortSerieVirtuel:
    def __init__(self):
        self.messages = []
    def write(self, message: bytes):
        self.messages.append(message)
        return len(message)
    def flush(self):
        pass


def main():
    port = PortSerieVirtuel()
    scenarios = [
        ("Presence enregistree", "ok", "GREEN"),
        ("Pointage deja enregistre", "deja", "WHITE"),
        ("Etudiant hors groupe", "hors_groupe", "WHITE"),
        ("Fenetre terminee", "ferme", "WHITE"),
        ("Carte inconnue", "inconnue", "WHITE"),
    ]
    for libelle, statut, attendu in scenarios:
        couleur = couleur_pour_statut(statut)
        assert couleur == attendu
        trame = envoyer_feedback(port, couleur)
        print(f"SIMULATION : {libelle} -> {trame.decode().strip()}")
    assert len(port.messages) == len(scenarios)
    print("Simulation Serial sans materiel : OK")


if __name__ == '__main__':
    main()
