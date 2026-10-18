import concurrent.futures
import socket
from rich.table import Table
from core.common import console, demander, titre, bad, warn, barre, nettoyer_cible, resoudre, BX, C_CYBER, C_GOLD

def scan_ports():
    warn("Uniquement sur tes propres machines ou avec autorisation.")
    cible = nettoyer_cible(demander("IP ou domaine"))
    ip = resoudre(cible)
    if not ip:
        bad("Impossible de résoudre la cible.")
        return
    titre(f"SCAN DE PORTS : {cible} ({ip})", C_CYBER)
    ports = {21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53:"DNS", 80: "HTTP",
             110: 'POP3', 143:'IMAP', 443: 'HTTPS', 445: 'SMB', 993: 'IMAPS',
             995: "POP3S", 1433: "MSSQL", 3306: "MySQL", 3389: "RDP",
             5432: "PostgreSQL", 5900: "VNC", 8080: "HTTP-alt", 8443: "HTTPS-alt"}

    def test(p):
        with socket.socket() as s:
            s.settimeout(1)
            return p, s.connect_ex((ip, p)) ==0

    ouverts = []
    with barre() as pr:
        tache = pr.add_task("Scan en cours", total=len(ports))
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as ex:
            futs = [ex.submit(test, p) for p in ports]
            for f in concurrent.futures.as_completed(futs):
                p, est_ouvert= f.result()
                if est_ouvert:
                    ouverts.append(p)
                pr.advance(tache)

    if not ouverts:
        bad('Aucun port courant ouvert.')
        return
    t = Table(box=BX, border_style=C_CYBER, header_style=f"bold {C_CYBER}")
    t.add_column('Port', style=f"bold {C_GOLD}", justify='right')
    t.add_column("Service")
    t.add_column("État")
    for p in sorted(ouverts):
        t.add_row(str(p), ports[p], "[bold green]OUVERT[/]")
    console.print(t)
