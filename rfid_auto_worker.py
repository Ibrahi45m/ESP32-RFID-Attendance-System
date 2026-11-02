"""Pointage RFID continu, indépendant de Streamlit.

Démarrer une seule instance : python rfid_auto_worker.py
RFID_PORT=COM7, RFID_SCAN_WINDOW=full|half|<minutes>.
N'ouvre jamais une DB autre que celle située à côté de database.py.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

from database import connect
from pointage_service import enregistrer_pointage, normaliser_uid
from rfid_led_feedback import couleur_pour_statut, envoyer_feedback

ROOT = Path(__file__).resolve().parent
STATUS_PATH = ROOT / "rfid_auto_status.json"
LOCK_PATH = ROOT / "rfid_auto_worker.lock"
SERIAL_BAUD = 115200
HEARTBEAT_SECONDS = 2
RETRY_SECONDS = 3
REPEAT_SECONDS = 2.0


class FiltreAntiRepetition:
    """Ignore un UID repasse dans les N secondes, meme apres une autre carte.

    Une autre seance constitue un contexte distinct. Pas de changement SQLite.
    """

    def __init__(self, delai: float = REPEAT_SECONDS):
        if delai <= 0:
            raise ValueError("Le delai doit etre positif.")
        self.delai = delai
        self._derniers: dict[tuple[object, str], float] = {}

    def ignorer(self, uid: str, instant: float, seance_id: object = None) -> bool:
        cle = (seance_id, uid)
        precedent = self._derniers.get(cle)
        if precedent is not None and 0 <= instant - precedent < self.delai:
            return True
        self._derniers[cle] = instant
        # Nettoyage opportuniste des cles anciennes pour les longues executions.
        if len(self._derniers) > 100:
            self._derniers = {
                k: t for k, t in self._derniers.items()
                if 0 <= instant - t < self.delai
            }
        return False



def configurer_fenetre(texte: str) -> tuple[str, int | None]:
    """full = toute la séance, half = moitié, N = N premières minutes."""
    valeur = texte.strip().lower()
    if valeur in ("full", "half"):
        return valeur, None
    if valeur.isdecimal() and int(valeur) > 0:
        return "minutes", int(valeur)
    raise ValueError("RFID_SCAN_WINDOW doit etre full, half ou un entier positif (minutes).")


def calculer_fin_pointage(debut: datetime, fin: datetime, mode: str, minutes: int | None) -> datetime:
    if fin <= debut:
        raise ValueError("Horaire invalide : la fin doit etre apres le debut.")
    if mode == "full":
        return fin
    if mode == "half":
        return debut + (fin - debut) / 2
    if mode == "minutes" and minutes is not None and minutes > 0:
        return min(fin, debut + timedelta(minutes=minutes))
    raise ValueError("Mode de fenetre invalide.")


def etat_seance(conn, maintenant: datetime, mode: str, minutes: int | None) -> dict:
    """Retourne le droit de scanner maintenant, sans modifier SQLite."""
    date_sql = maintenant.strftime("%Y-%m-%d")
    heure_sql = maintenant.strftime("%H:%M")
    seances = conn.execute("""
        SELECT id, module, date, heure_debut, heure_fin
        FROM seances
        WHERE date = ? AND heure_debut <= ? AND heure_fin > ?
        ORDER BY id
    """, (date_sql, heure_sql, heure_sql)).fetchall()

    if not seances:
        prochaine = conn.execute("""
            SELECT module, heure_debut FROM seances
            WHERE date = ? AND heure_debut > ?
            ORDER BY heure_debut, id LIMIT 1
        """, (date_sql, heure_sql)).fetchone()
        if prochaine:
            return {
                "code": "attente",
                "message": f"Fenetre de pointage non ouverte. Prochaine seance : {prochaine[0]} a {prochaine[1]}.",
            }
        return {"code": "attente", "message": "Aucune seance en cours."}
    if len(seances) > 1:
        return {"code": "conflit", "message": "Plusieurs seances actives : aucun pointage."}

    seance_id, module, date, debut_str, fin_str = seances[0]
    debut = datetime.fromisoformat(f"{date}T{debut_str}")
    fin = datetime.fromisoformat(f"{date}T{fin_str}")
    limite = calculer_fin_pointage(debut, fin, mode, minutes)
    base = {
        "seance_id": seance_id, "module": module,
        "debut": debut_str, "fin": fin_str,
        "limite": limite.strftime("%H:%M:%S"),
    }

    if maintenant >= limite:
        # Une autre seance peut commencer plus tard : ne pas confondre sa
        # fenetre non ouverte avec celle de la seance courante deja terminee.
        prochaine = conn.execute("""
            SELECT module, heure_debut FROM seances
            WHERE date = ? AND heure_debut > ?
            ORDER BY heure_debut, id LIMIT 1
        """, (date_sql, heure_sql)).fetchone()
        message = "Fenetre de pointage terminee."
        if prochaine:
            message += f" Fenetre non ouverte pour {prochaine[0]} avant {prochaine[1]}."
        return {**base, "code": "ferme", "message": message}

    groupe = conn.execute(
        "SELECT 1 FROM seance_groupes WHERE seance_id = ? LIMIT 1",
        (seance_id,),
    ).fetchone()
    if groupe is None:
        return {**base, "code": "sans_groupe", "message": "Seance sans groupe : pointage refuse."}
    return {**base, "code": "actif", "message": "Pointage automatique actif."}


def etat_actuel(mode: str, minutes: int | None, maintenant: datetime | None = None) -> dict:
    conn = connect()
    try:
        return etat_seance(conn, maintenant or datetime.now(), mode, minutes)
    finally:
        conn.close()


def ecrire_statut(statut: dict) -> None:
    """Le dashboard lit un JSON, pas le port serie; écriture atomique."""
    etat = {**statut, "heartbeat": datetime.now().isoformat(timespec="seconds"), "pid": os.getpid()}
    temporaire = STATUS_PATH.with_name(STATUS_PATH.name + f".{os.getpid()}.tmp")
    temporaire.write_text(json.dumps(etat, ensure_ascii=False), encoding="utf-8")
    os.replace(temporaire, STATUS_PATH)


def verrou_processus():
    """Bloque une deuxième instance du worker dans le même dossier."""
    handle = open(LOCK_PATH, "a+b")
    try:
        if os.name == "nt":
            import msvcrt
            handle.seek(0)
            if handle.read(1) == b"":
                handle.seek(0)
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (OSError, BlockingIOError):
        handle.close()
        raise RuntimeError("Un pointage automatique tourne deja pour ce projet.")
    return handle


def main() -> None:
    # Le port reste ouvert entre les cartes; on n'attend jamais un clic Streamlit.
    try:
        import serial
    except ImportError as exc:
        raise RuntimeError("PySerial manquant : python -m pip install pyserial") from exc

    port = os.getenv("RFID_PORT", "COM7")
    mode, minutes = configurer_fenetre(os.getenv("RFID_SCAN_WINDOW", "full"))
    lock = verrou_processus()
    filtre_repetition = FiltreAntiRepetition()
    dernier_heartbeat = 0.0
    dernier_resultat = None
    lecteur = None

    print(f"Mode AUTO | Port {port} | Fenetre {os.getenv('RFID_SCAN_WINDOW', 'full')}", flush=True)
    print("Ouvrez cette fenetre avant la seance et laissez-la ouverte.", flush=True)
    try:
        while True:
            if lecteur is None:
                try:
                    lecteur = serial.Serial(port, SERIAL_BAUD, timeout=0.3)
                    time.sleep(2)  # Redemarrage ESP32 possible a l'ouverture du port
                    print(f"Lecteur connecte : {port}", flush=True)
                except (serial.SerialException, OSError) as exc:
                    if lecteur is not None:
                        try:
                            lecteur.close()
                        except Exception:
                            pass
                    lecteur = None
                    ecrire_statut({"lecteur": "deconnecte", "fenetre": "attente", "message": str(exc), "dernier_resultat": dernier_resultat})
                    print(f"Lecteur indisponible ({port}) : {exc}; nouvel essai...", flush=True)
                    time.sleep(RETRY_SECONDS)
                    continue

            try:
                maintenant = datetime.now()
                etat = etat_actuel(mode, minutes, maintenant)
                if time.monotonic() - dernier_heartbeat >= HEARTBEAT_SECONDS:
                    ecrire_statut({"lecteur": "connecte", "fenetre": etat["code"],
                                   "message": etat["message"], "seance": etat,
                                   "dernier_resultat": dernier_resultat})
                    dernier_heartbeat = time.monotonic()

                ligne = lecteur.readline().decode("utf-8", errors="replace").strip()
                if ligne.startswith("LED_SIM:"):
                    print(f"ESP32 ACK : {ligne}", flush=True)
                    continue
                if not ligne.startswith("Card UID:"):
                    continue
                uid = normaliser_uid(ligne.split(":", 1)[1])
                if not uid:
                    continue
                # Recalcul au moment precis du passage de la carte.
                horodatage = datetime.now()
                etat = etat_actuel(mode, minutes, horodatage)
                instant = time.monotonic()
                if filtre_repetition.ignorer(uid, instant, etat.get("seance_id")):
                    continue
                if etat["code"] != "actif":
                    # Le PC refuse le pointage : envoyer la simulation LED blanche.
                    envoyer_feedback(lecteur, "WHITE")
                    dernier_resultat = {
                        "statut": etat["code"], "etudiant": "", "module": etat.get("module", ""),
                        "message": f"Carte ignoree : {etat['message']}",
                        "heure": horodatage.strftime("%H:%M:%S"),
                    }
                    print(dernier_resultat["message"], flush=True)
                    ecrire_statut({"lecteur": "connecte", "fenetre": etat["code"],
                                   "message": etat["message"], "seance": etat,
                                   "dernier_resultat": dernier_resultat})
                    dernier_heartbeat = time.monotonic()
                    continue

                # Une erreur de verification ne doit jamais allumer la LED verte.
                try:
                    resultat = enregistrer_pointage(uid, maintenant=horodatage)
                except Exception:
                    envoyer_feedback(lecteur, "WHITE")
                    raise
                envoyer_feedback(lecteur, couleur_pour_statut(resultat.statut))
                dernier_resultat = {
                    "statut": resultat.statut,
                    "etudiant": resultat.etudiant,
                    "module": resultat.module,
                    "message": resultat.message,
                    "heure": datetime.now().strftime("%H:%M:%S"),
                }
                print(f"{dernier_resultat['heure']} | {resultat.etudiant or 'Carte'} | {resultat.message}", flush=True)
                ecrire_statut({"lecteur": "connecte", "fenetre": etat["code"],
                               "message": etat["message"], "seance": etat,
                               "dernier_resultat": dernier_resultat})
                dernier_heartbeat = time.monotonic()

            except (serial.SerialException, OSError) as exc:
                print(f"Connexion perdue : {exc}", flush=True)
                try:
                    lecteur.close()
                except Exception:
                    pass
                lecteur = None
                time.sleep(RETRY_SECONDS)
            except Exception as exc:
                # Une erreur SQLite n'arrete pas la lecture et peut etre corrigee.
                print(f"Erreur de traitement : {exc}", flush=True)
                ecrire_statut({"lecteur": "connecte", "fenetre": "erreur",
                               "message": str(exc), "dernier_resultat": dernier_resultat})
                time.sleep(1)

    except KeyboardInterrupt:
        print("Arret du pointage automatique.", flush=True)
    finally:
        if lecteur is not None:
            lecteur.close()
        lock.close()
        # Le dashboard detectera l'arret par le heartbeat.


if __name__ == "__main__":
    main()
