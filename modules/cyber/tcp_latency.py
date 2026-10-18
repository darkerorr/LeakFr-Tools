import time
import socket
from core.common import demander, titre, bad, warn, kv, barre, nettoyer_cible, resoudre, C_CYBER

def latence_tcp():
    warn('Uniquement sur des cibles autorisées.')
    cible = nettoyer_cible(demander("Hôte"))
    ip =resoudre(cible.split(":")[0])
    if not ip:
        bad("Résolution impossible.")
        return
    port_s =demander('Port', defaut='443')
    try:
        port =int(port_s)
    except ValueError:
        bad("Port invalide.")
        return
    titre(f"LATENCE TCP : {cible}:{port} ({ip})", C_CYBER)
    mesures =[]
    banner =""
    with barre() as pr:
        tache = pr.add_task("Mesures", total=5)
        for _ in range(5):
            t0 =time.time()
            try:
                with socket.create_connection((ip, port), timeout=2) as s:
                    ms = (time.time() - t0) * 1000
                    mesures.append(ms)
                    s.settimeout(0.4)
                    try:
                        if not banner:
                            if port in (80, 8080):
                                s.sendall(b'HEAD / HTTP/1.0\r\n\r\n')
                            data =s.recv(256)
                            if data:
                                banner =data.decode(errors='ignore').split('\n')[0][:80]
                    except Exception:
                        pass
            except Exception:
                mesures.append(None)
            pr.advance(tache)
            time.sleep(0.15)
    ok_ms = [m for m in mesures if m is not None]
    if not ok_ms:
        bad('Connexion impossible.')
        return
    kv("Résultats", [
        ('Réussites', f"{len(ok_ms)}/5"),
        ("Min", f"{min(ok_ms):.1f} ms"),
        ("Moy", f"{sum(ok_ms) / len(ok_ms):.1f} ms"),
        ('Max', f"{max(ok_ms):.1f} ms"),
        ("Banner", banner or "-"),
    ], C_CYBER)
