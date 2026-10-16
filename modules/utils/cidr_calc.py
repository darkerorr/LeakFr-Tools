import ipaddress
from core.common import demander, titre, bad, kv, C_UTIL

def calc_reseau():
    titre("CALCULATEUR CIDR / SOUS-RÉSEAU", C_UTIL)
    saisie = demander("Réseau (ex: 192.168.1.0/24 ou 10.0.0.5/28)")
    try:
        net = ipaddress.ip_network(saisie, strict=False)
    except ValueError as e:
        bad(f"Invalide : {e}")
        return
    hosts = list(net.hosts())
    kv("Réseau", [
        ("CIDR", str(net)),
        ("Adresse réseau", str(net.network_address)),
        ("Broadcast", str(net.broadcast_address) if net.version == 4 else "N/A (IPv6)"),
        ("Masque", str(net.netmask)),
        ("Wildcard", str(net.hostmask)),
        ("Préfixe", f"/{net.prefixlen}"),
        ("Adresses totales", net.num_addresses),
        ("Hôtes utilisables", max(0, net.num_addresses - (2 if net.version == 4 and net.prefixlen < 31 else 0))),
        ("Premier hôte", str(hosts[0]) if hosts else "-"),
        ("Dernier hôte", str(hosts[-1]) if hosts else "-"),
    ], C_UTIL)
