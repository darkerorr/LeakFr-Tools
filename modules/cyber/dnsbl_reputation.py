import re
import concurrent.futures
import socket
from rich.table import Table
from core.common import console, demander, titre, ok, bad, warn, barre, nettoyer_cible, resoudre, BX, C_CYBER, OKC, KOC

def dnsbl_check():
    cible = nettoyer_cible(demander("IP à tester (listes noires)"))
    ip = cible if re.match(r"^\d+\.\d+\.\d+\.\d+$", cible) else resoudre(cible)
    if not ip:
        bad("IP invalide.")
        return
    titre(f"DNSBL / RÉPUTATION : {ip}", C_CYBER)
    rev = ".".join(reversed(ip.split(".")))
    listes = [
        ("zen.spamhaus.org", "Spamhaus ZEN"),
        ("bl.spamcop.net", "SpamCop"),
        ("b.barracudacentral.org", "Barracuda"),
        ("dnsbl.sorbs.net", "SORBS"),
        ("cbl.abuseat.org", "CBL Abuseat"),
    ]

    def check(item):
        zone, nom = item
        try:
            socket.gethostbyname(f"{rev}.{zone}")
            return nom, True
        except socket.gaierror:
            return nom, False

    rows = []
    with barre() as pr:
        tache = pr.add_task("Consultation DNSBL", total=len(listes))
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
            for f in concurrent.futures.as_completed([ex.submit(check, x) for x in listes]):
                rows.append(f.result())
                pr.advance(tache)
    t = Table(box=BX, border_style=C_CYBER, header_style=f"bold {C_CYBER}")
    t.add_column("Liste")
    t.add_column("Statut")
    listes_ok = 0
    for nom, liste in rows:
        if liste:
            listes_ok += 1
            t.add_row(nom, f"[bold red]{KOC} LISTÉ[/]")
        else:
            t.add_row(nom, f"[bold green]{OKC} clean[/]")
    console.print(t)
    if listes_ok:
        warn(f"Présent dans {listes_ok} liste(s).")
    else:
        ok("Aucune des listes courantes ne signale cette IP.")
