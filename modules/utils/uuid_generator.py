"""Génération locale d'identifiants UUID v4."""
import uuid

from rich.table import Table

from core.common import BX, C_UTIL, console, demander, titre, warn


def generer_uuid():
    titre("GENERATEUR UUID v4", C_UTIL)
    quantite_txt = demander("Nombre d'UUID (1-50)", defaut="1")
    if not quantite_txt.isdigit() or not 1 <= int(quantite_txt) <= 50:
        warn("Le nombre doit etre compris entre 1 et 50.")
        return
    table = Table(box=BX, border_style=C_UTIL, header_style=f"bold {C_UTIL}")
    table.add_column("#", justify="right")
    table.add_column("UUID v4", style="bold")
    for index in range(int(quantite_txt)):
        table.add_row(str(index + 1), str(uuid.uuid4()))
    console.print(table)
