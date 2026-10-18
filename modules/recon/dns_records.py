from rich.table import Table
from rich.markup import escape
from core.common import console, demander, titre, bad, attente, nettoyer_cible, doh, BX, C_RECON, C_GOLD

def dns_lookup():
    domaine = nettoyer_cible(demander('Domaine'))
    titre(f"ENREGISTREMENTS DNS : {domaine}", C_RECON)
    t = Table(box=BX, border_style=C_RECON, header_style=f"bold {C_RECON}")
    t.add_column('Type', style=f"bold {C_GOLD}")
    t.add_column("Valeur")
    trouve= False
    with attente('Requêtes DNS'):
        for typ in ["A", "AAAA", "MX", "NS", "TXT", "CNAME"]:
            for x in doh(domaine, typ):
                t.add_row(typ, escape(x))
                trouve =True
    if trouve:
        console.print(t)
    else:
        bad("Aucun enregistrement trouvé.")
