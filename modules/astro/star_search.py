import requests
from core.common import console, demander, titre, bad, kv, attente, C_ASTRO

def recherche_astre():
    titre("RECHERCHE D'UN ASTRE (SIMBAD)", C_ASTRO)
    console.print("[dim]Exemples : Sirius, Betelgeuse, Vega, Polaris, Andromeda Galaxy[/]\n")
    nom = demander("Nom de l'astre")
    if not nom:
        return
    variantes = []
    for n in (nom, nom.title()):
        for pre in ("", "NAME ", "* "):
            v = pre + n
            if v not in variantes:
                variantes.append(v)
    ids = ", ".join("'" + v.replace("'", "''") + "'" for v in variantes)
    adql = ("SELECT TOP 1 main_id, ra, dec, otype, sp_type, plx_value, pmra, pmdec "
            "FROM basic JOIN ident ON oidref = oid WHERE id IN (" + ids + ")")
    try:
        with attente("Interrogation de SIMBAD (CDS Strasbourg)"):
            r = requests.get("https://simbad.cds.unistra.fr/simbad/sim-tap/sync",
                             params={"request": "doQuery", "lang": "adql",
                                     "format": "json", "query": adql}, timeout=30)
            j = r.json()
    except Exception as e:
        bad(f"Erreur : {e}")
        return
    data = j.get("data") or []
    if not data:
        bad("Astre introuvable. Essaie un autre nom (ex: 'Sirius', 'Vega').")
        return
    champs = [m["name"] for m in j["metadata"]]
    d = dict(zip(champs, data[0]))

    def hms(ra):
        h = ra / 15
        hh = int(h)
        mm = int((h - hh) * 60)
        ss = ((h - hh) * 60 - mm) * 60
        return f"{hh:02d}h {mm:02d}m {ss:05.2f}s"

    def dms(dec):
        s = "-" if dec < 0 else "+"
        dec = abs(dec)
        dd = int(dec)
        mm = int((dec - dd) * 60)
        ss = ((dec - dd) * 60 - mm) * 60
        return f"{s}{dd:02d}° {mm:02d}' {ss:04.1f}\""

    lignes = [("Identifiant", d.get("main_id")), ("Type d'objet", d.get("otype"))]
    if d.get("ra") is not None and d.get("dec") is not None:
        lignes += [("Ascension droite", hms(d["ra"])), ("Déclinaison", dms(d["dec"]))]
    if d.get("sp_type"):
        lignes.append(("Type spectral", d["sp_type"]))
    plx = d.get("plx_value")
    if plx and plx > 0:
        ly = 3261.56 / plx
        lignes.append(("Parallaxe", f"{plx:.3f} mas"))
        lignes.append(("Distance", f"~{ly:,.1f} années-lumière".replace(",", " ")))
    if d.get("pmra") is not None and d.get("pmdec") is not None:
        lignes.append(("Mouvement propre", f"{d['pmra']:.2f} / {d['pmdec']:.2f} mas/an"))
    kv(f"Résultat pour : {nom}", lignes, C_ASTRO)
