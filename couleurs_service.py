"""Association persistante couleur-module, non destructive."""

PALETTE = [f"hsl({hue}, 75%, 43%)" for hue in range(0, 360, 30)]


def synchroniser_couleurs(conn):
    """Ajoute les nouveaux modules sans changer les couleurs déjà attribuées.

    IMPORTANT : appeler avec une connexion SQLite ouverte, puis committer.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS couleurs_modules (
            module TEXT PRIMARY KEY,
            couleur TEXT NOT NULL UNIQUE
        )
    """)
    disponibles = conn.execute("""
        SELECT DISTINCT module FROM seances ORDER BY module COLLATE NOCASE
    """).fetchall()
    existantes = dict(conn.execute("SELECT module, couleur FROM couleurs_modules").fetchall())
    utilisees = set(existantes.values())

    for (module,) in disponibles:
        if module in existantes:
            continue
        candidats = list(PALETTE)
        for luminosite in (35, 52, 62, 28):
            for hue in range(0, 360, 15):
                candidats.append(f"hsl({hue}, 75%, {luminosite}%)")

        couleur = next((candidate for candidate in candidats if candidate not in utilisees), None)
        if couleur is None:
            raise ValueError("Nombre maximum de couleurs distinctes atteint.")

        conn.execute("""
            INSERT INTO couleurs_modules (module, couleur) VALUES (?, ?)
        """, (module, couleur))
        existantes[module] = couleur
        utilisees.add(couleur)

    conn.commit()
    return existantes


def nettoyer_couleur_orpheline(conn, module):
    """Enlève la couleur seulement s'il n'existe plus de séance liée."""
    return conn.execute("""
        DELETE FROM couleurs_modules
        WHERE module = ?
          AND NOT EXISTS (SELECT 1 FROM seances WHERE module = ?)
    """, (module, module)).rowcount
