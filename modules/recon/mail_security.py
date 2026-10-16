from core.common import demander, titre, ok, kv, attente, nettoyer_cible, doh, C_RECON, KOC

def spf_dmarc():
    domaine = nettoyer_cible(demander("Domaine email (ex: gmail.com)"))
    if not domaine:
        return
    titre(f"SÉCURITÉ EMAIL (SPF / DMARC / DKIM) : {domaine}", C_RECON)
    with attente("Requêtes DNS"):
        txt = doh(domaine, "TXT")
        mx = doh(domaine, "MX")
        dmarc = doh(f"_dmarc.{domaine}", "TXT")
        selectors = []
        for sel in ("default", "google", "selector1", "selector2", "k1", "s1", "s2", "dkim"):
            recs = doh(f"{sel}._domainkey.{domaine}", "TXT")
            if recs:
                selectors.append((sel, recs[0][:120]))
    spf = [x for x in txt if "v=spf1" in x.lower()]
    dmarc_recs = [x for x in dmarc if "v=dmarc1" in x.lower()]
    lignes = [
        ("MX", "\n".join(mx) if mx else f"{KOC} aucun"),
        ("SPF", "\n".join(spf) if spf else f"{KOC} absent"),
        ("DMARC", "\n".join(dmarc_recs) if dmarc_recs else f"{KOC} absent"),
    ]
    if selectors:
        lignes.append(("DKIM (sélecteurs)",
                       "\n".join(f"{s}: {v}..." for s, v in selectors)))
    else:
        lignes.append(("DKIM", f"{KOC} aucun sélecteur courant trouvé"))
    kv("Résultat", lignes, C_RECON)
    score = sum([bool(mx), bool(spf), bool(dmarc_recs), bool(selectors)])
    ok(f"Score config mail : {score}/4")
