"""Génération locale de cas limites HTTP, sans émission de requêtes réseau."""
import json
from pathlib import Path

from core.common import C_UTIL, demander, kv, titre, warn, ok


def construire_corpus_http():
    """Retourne des fixtures structurées, y compris des valeurs de protocole limites."""
    return {
        "schema": "leakfr.http-edge-corpus.v1",
        'usage': 'Fixtures de test pour un serveur ou un parseur HTTP local autorisé.',
        "network_requests": False,
        "cases": [
            {'id': 'baseline-normal', 'class': 'baseline', 'headers': [['X-Lab-Case', 'baseline']]},
            {"id": "empty-value", "class": "boundary", "headers": [["X-Lab-Case", ""]]},
            {"id": "leading-trailing-space", "class": "whitespace", "headers": [["X-Lab-Case", "  padded value  "]]},
            {'id':'tab-in-value', 'class':'whitespace', 'headers':[['X-Lab-Case', 'left\tright']]},
            {"id": "duplicate-identical", "class": "duplicate", "headers":[["X-Lab-Case", "same"], ["X-Lab-Case", "same"]]},
            {"id": "duplicate-conflicting", "class": "duplicate", "headers": [["X-Lab-Case", "first"], ["X-Lab-Case", "second"]]},
            {'id': 'case-variant-name', 'class': 'case-folding', 'headers': [['x-lab-case', 'lower'], ['X-LAB-CASE', 'upper']]},
            {"id": "comma-list", "class": "list-merge", "headers": [["X-Lab-Case", "alpha, beta"]]},
            {"id":"unicode-value", "class": "unicode", "headers": [["X-Lab-Case", "café-日本語-🔬"]]},
            {'id': 'crlf-in-value', 'class':'invalid-control', 'headers':[['X-Lab-Case', 'first\r\nX-Lab-Injected: second']]},
            {"id": "nul-in-value", "class": "invalid-control", "headers": [["X-Lab-Case", "left\x00right"]]},
            {"id": "invalid-name-space", "class": "invalid-name", "headers":[["X Lab Case", "value"]]},
            {'id': 'invalid-name-colon', 'class': 'invalid-name', 'headers': [['X:Lab', 'value']]},
            {"id":"oversized-value-8k", "class": "size-boundary", "headers": [["X-Lab-Case", "A" * 8192]]},
            {"id": "forwarded-loopback", "class":"forwarding-metadata", "headers": [["Forwarded", "for=127.0.0.1;proto=http;host=lab.invalid"]]},
            {'id': 'content-length-zero', 'class':'framing-metadata', 'headers': [['Content-Length', '0']]},
            {"id": "transfer-encoding-chunked", "class":"framing-metadata", "headers": [["Transfer-Encoding", "chunked"]]},
            {"id": "conflicting-framing", "class": "framing-ambiguity", "headers":[["Content-Length", "4"], ["Transfer-Encoding", "chunked"]]},
            {'id':'method-override', 'class': 'method-override', 'headers': [['X-HTTP-Method-Override', 'DELETE']]},
            {"id": "untrusted-hostname", "class":"host-routing", "headers": [["Host", "lab.invalid"]]},
        ],
    }


def generer_corpus_http():
    """Écrit un corpus JSON pour un laboratoire local ; aucune cible n'est contactée."""
    titre("GENERATEUR DE CORPUS HTTP - LOCAL UNIQUEMENT", C_UTIL)
    destination = demander('Fichier JSON de sortie', 'http-edge-corpus.json').strip()
    if not destination:
        warn("Chemin vide : aucun fichier créé.")
        return
    chemin= Path(destination).expanduser()
    corpus = construire_corpus_http()
    try:
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(json.dumps(corpus, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        warn(f"Impossible d'écrire le corpus : {exc}")
        return
    kv('Corpus HTTP généré', [('Fichier', chemin), ('Cas', len(corpus['cases'])), ('Réseau', 'Aucune requête émise')], C_UTIL)
    ok("Fixtures créées. Utilisez-les uniquement sur un serveur/parseur de laboratoire autorisé.")
