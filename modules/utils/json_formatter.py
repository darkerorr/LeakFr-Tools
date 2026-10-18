"""Validation et formatage JSON local à partir d'un texte collé."""
import json

from rich.prompt import Confirm

from core.common import C_UTIL, bad, console, demander, titre


def formater_json():
    titre("FORMATEUR JSON", C_UTIL)
    source= demander("Collez le JSON a valider/formater")
    try:
        data= json.loads(source)
    except json.JSONDecodeError as exc:
        bad(f"JSON invalide ligne {exc.lineno}, colonne {exc.colno} : {exc.msg}")
        return
    compact= Confirm.ask("Sortie compacte (sinon mise en forme lisible) ?", default=False)
    trier = Confirm.ask('Trier les cles alphabetiquement ?', default=False)
    sortie = json.dumps(data, ensure_ascii=False, sort_keys=trier,
                        separators=(",", ":") if compact else None,
                        indent=None if compact else 2)
    console.print(sortie, markup=False, style="shell.text")
