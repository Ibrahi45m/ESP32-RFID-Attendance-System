"""Protocole serie minimal pour la simulation de deux LEDs.

Python est seule source de verite (SQLite) : GREEN seulement pour statut 'ok'.
L'ESP32 doit un jour ecouter les commandes ASCII LED:GREEN / LED:WHITE.
"""
from __future__ import annotations

COULEURS = frozenset({"GREEN", "WHITE"})


def couleur_pour_statut(statut: str) -> str:
    """Le deja, hors groupe, carte inconnue et fenetre fermee ne valident pas un nouveau pointage."""
    return "GREEN" if statut == "ok" else "WHITE"


def encoder_commande(couleur: str) -> bytes:
    if couleur not in COULEURS:
        raise ValueError(f"Couleur invalide : {couleur!r}")
    return f"LED:{couleur}\n".encode("ascii")


def envoyer_feedback(serie, couleur: str, afficher=print) -> bytes:
    """Envoi la commande au port serie deja ouvert; n'ouvre aucun second COM."""
    trame = encoder_commande(couleur)
    n = serie.write(trame)
    if n is not None and n != len(trame):
        raise OSError(f"Ecriture serie incomplete : {n}/{len(trame)} octets")
    serie.flush()
    afficher(f"LED TX -> ESP32 : {couleur} (simulation, sans LED physique)", flush=True)
    return trame
