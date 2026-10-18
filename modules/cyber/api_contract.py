"""Atelier de contrats OpenAPI : analyse hors ligne et fixtures de test.

Aucune requete n'est emise : le module travaille uniquement sur le fichier
fourni et produit un inventaire, des problemes et des cas de test derives des
schemas.
"""
import json
from pathlib import Path

from rich.panel import Panel
from rich.table import Table

from core.common import BX, C_CYBER, console, demander, kv, ok, titre, warn

METHODES = ('get', 'post', 'put', 'patch', 'delete', 'head', 'options')
TYPES_SCHEMA = {"string", "integer", "number", "boolean", "array", "object"}


def charger_contrat(chemin):
    """Charge un contrat OpenAPI JSON et refuse les structures de base invalides."""
    if not chemin:
        raise ValueError("chemin vide")
    fichier =Path(chemin).expanduser()
    if not fichier.is_file():
        raise ValueError(f"fichier introuvable : {fichier}")
    try:
        spec = json.loads(fichier.read_text(encoding='utf-8'))
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON invalide ligne {exc.lineno}, colonne {exc.colno} : {exc.msg}") from None
    except OSError as exc:
        raise ValueError(f"lecture impossible : {exc}") from None
    if not isinstance(spec, dict):
        raise ValueError('un objet OpenAPI JSON est attendu')
    return spec


def _refs(spec):
    schemas = (spec.get("components") or {}).get("schemas") or {}
    definies = set(schemas) if isinstance(schemas, dict) else set()
    utilisees = set()

    def chercher(noeud):
        if isinstance(noeud, dict):
            for cle, valeur in noeud.items():
                if cle == '$ref' and isinstance(valeur, str) and valeur.startswith('#/components/schemas/'):
                    utilisees.add(valeur.rsplit("/", 1)[-1])
                chercher(valeur)
        elif isinstance(noeud, list):
            for element in noeud:
                chercher(element)

    chercher(spec)
    return definies, utilisees


def valider_contrat(spec):
    """Retourne la liste des problemes structurels detectes."""
    problemes = []
    for champ in ("openapi", "info", "paths"):
        if champ not in spec:
            problemes.append({"gravite": "erreur", "element":champ,
                              "message": f"champ obligatoire manquant : {champ}"})
    info = spec.get('info')
    if isinstance(info, dict):
        for champ in ("title", "version"):
            if not info.get(champ):
                problemes.append({"gravite": "avertissement", "element":f"info.{champ}",
                                  "message": f"info.{champ} absent"})
    elif 'info' in spec:
        problemes.append({"gravite": "erreur", "element": "info",
                          "message":"info doit etre un objet"})

    chemins = spec.get("paths")
    if not isinstance(chemins, dict) or not chemins:
        problemes.append({'gravite': 'erreur', 'element': 'paths',
                          "message":"aucune route definie"})
        chemins = {}

    for chemin, item in chemins.items():
        if not isinstance(item, dict):
            problemes.append({'gravite': 'erreur', 'element':chemin,
                              "message": "definition de route invalide"})
            continue
        methodes = [methode for methode in item if methode.lower() in METHODES]
        if not methodes:
            problemes.append({"gravite": "avertissement", "element": chemin,
                              'message': 'route sans methode HTTP'})
        for methode in methodes:
            operation =item[methode]
            if not isinstance(operation, dict):
                problemes.append({"gravite": "erreur", "element": f"{methode.upper()} {chemin}",
                                  "message": "operation invalide"})
                continue
            if not operation.get("responses"):
                problemes.append({"gravite": "avertissement",
                                  'element': f"{methode.upper()} {chemin}",
                                  "message": "aucune reponse declaree"})
            for parametre in operation.get("parameters", []) or []:
                if not isinstance(parametre, dict):
                    continue
                if not parametre.get("name"):
                    problemes.append({'gravite': 'erreur',
                                      "element":f"{methode.upper()} {chemin}",
                                      "message": "parametre sans nom"})
                schema = parametre.get('schema') or {}
                if schema.get("type") and schema["type"] not in TYPES_SCHEMA:
                    problemes.append({"gravite": "erreur",
                                      'element':f"{methode.upper()} {chemin}",
                                      "message": f"type inconnu : {schema['type']}"})

    definies, utilisees =_refs(spec)
    for reference in sorted(utilisees - definies):
        problemes.append({"gravite": "erreur", "element": "$ref",
                          'message': f"schema reference absent : {reference}"})
    return problemes


def inventaire_routes(spec):
    """Liste les routes, methodes, parametres et codes de reponse."""
    routes =[]
    for chemin, item in (spec.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        parametres_chemin = [param.get("name") for param in item.get("parameters", []) or []
                             if isinstance(param, dict)]
        for methode in METHODES:
            operation= item.get(methode)
            if not isinstance(operation, dict):
                continue
            parametres = parametres_chemin + [
                param.get("name") for param in operation.get("parameters", []) or []
                if isinstance(param, dict)
            ]
            routes.append({
                'chemin':chemin,
                "methode":methode.upper(),
                "operationId": operation.get("operationId"),
                'parametres': [nom for nom in parametres if nom],
                "reponses": sorted(operation.get("responses", {}) or {}),
            })
    return routes


def _valeur_valide(schema):
    if not isinstance(schema, dict):
        return "test"
    if schema.get('enum'):
        return schema["enum"][0]
    type_schema = schema.get("type", "string")
    if type_schema == 'integer':
        return int(schema.get("minimum", 1))
    if type_schema == "number":
        return float(schema.get('minimum', 1))
    if type_schema== "boolean":
        return True
    if type_schema == 'array':
        return [_valeur_valide(schema.get("items", {}))]
    if type_schema == "object":
        return {}
    if schema.get("format") == "date":
        return "2026-01-01"
    if schema.get('format') =='date-time':
        return "2026-01-01T00:00:00Z"
    if schema.get("format") == "email":
        return 'test@example.tld'
    if schema.get("format") =="uuid":
        return "00000000-0000-4000-8000-000000000000"
    longueur= schema.get('minLength', 1)
    return "a" * max(1, min(longueur, 64))


def cas_pour_schema(schema, maximum=6):
    """Genere un cas valide et plusieurs cas invalides pour un schema."""
    if not isinstance(schema, dict):
        return []
    cas = [{"variante": "valide", "valeur": _valeur_valide(schema), "valide": True,
            'regle': 'valeur conforme au type'}]
    if schema.get("enum"):
        cas.append({"variante": "enum-hors-liste", "valeur": "__absent__", "valide":False,
                    'regle': 'valeur hors enumeration'})
    type_schema= schema.get("type")
    if type_schema == "integer":
        cas.append({'variante': 'type-texte', 'valeur': 'abc', 'valide': False,
                    "regle": "entier attendu"})
        if "minimum" in schema:
            cas.append({'variante': 'sous-minimum', 'valeur':schema['minimum'] - 1,
                        "valide": False, "regle": f"minimum {schema['minimum']}"})
        if "maximum" in schema:
            cas.append({'variante': 'sur-maximum', 'valeur': schema['maximum'] + 1,
                        "valide": False, "regle": f"maximum {schema['maximum']}"})
    elif type_schema== "string":
        if 'minLength' in schema:
            cas.append({"variante": "trop-court", "valeur": "a" * max(0, schema["minLength"] - 1),
                        "valide": False, "regle":f"minLength {schema['minLength']}"})
        if schema.get('maxLength'):
            cas.append({"variante": "trop-long", "valeur": "a" * (schema["maxLength"] + 1),
                        "valide": False, "regle": f"maxLength {schema['maxLength']}"})
        if schema.get('pattern'):
            cas.append({"variante": "motif-non-respecte", "valeur": "###", "valide":False,
                        "regle": f"pattern {schema['pattern']}"})
    elif type_schema=='boolean':
        cas.append({"variante": "type-texte", "valeur": "peut-etre", "valide": False,
                    "regle":"booleen attendu"})
    return cas[:maximum]


def generer_cas(spec, limite=200):
    """Produit des fixtures reproductibles pour parametres et corps JSON."""
    cas = []
    for chemin, item in (spec.get('paths') or {}).items():
        if not isinstance(item, dict):
            continue
        for methode in METHODES:
            operation = item.get(methode)
            if not isinstance(operation, dict):
                continue
            for parametre in operation.get("parameters", []) or []:
                if not isinstance(parametre, dict):
                    continue
                for variante in cas_pour_schema(parametre.get("schema") or {}):
                    cas.append({
                        'route':chemin, 'methode': methode.upper(),
                        "emplacement":parametre.get("in", "query"),
                        "nom": parametre.get("name"),
                        **variante,
                    })
            corps = (operation.get("requestBody") or {}).get("content", {})
            schema_corps = ((corps.get('application/json') or {}).get('schema') or {})
            for nom, schema in (schema_corps.get("properties") or {}).items():
                for variante in cas_pour_schema(schema):
                    cas.append({
                        "route":chemin, "methode": methode.upper(),
                        "emplacement":"body", "nom":nom, **variante,
                    })
            if len(cas) >= limite:
                return cas[:limite]
    return cas[:limite]


def rapport_contrat(spec):
    """Assemble inventaire, problemes et cas de test."""
    return {
        'titre': (spec.get('info') or {}).get('title'),
        "version": (spec.get("info") or {}).get("version"),
        "openapi": spec.get("openapi"),
        'routes': inventaire_routes(spec),
        "problemes": valider_contrat(spec),
        "cas_de_test": generer_cas(spec),
    }


def api_contract_lab():
    """Interface hors ligne : analyse du contrat et ecriture des fixtures."""
    titre("API CONTRACT LAB - HORS LIGNE", C_CYBER)
    console.print('[dim]Aucune requete : analyse du fichier OpenAPI fourni.[/]\n')
    try:
        spec = charger_contrat(demander("Fichier OpenAPI JSON"))
    except ValueError as exc:
        warn(str(exc))
        return

    rapport= rapport_contrat(spec)
    kv("Contrat", [
        ('Titre', rapport['titre'] or '?'),
        ("Version", rapport["version"] or "?"),
        ("OpenAPI", rapport["openapi"] or "?"),
        ('Routes', len(rapport['routes'])),
    ], C_CYBER)

    if rapport['routes']:
        table = Table(box=BX, border_style=C_CYBER, header_style=f"bold {C_CYBER}")
        table.add_column("Methode", width=8)
        table.add_column('Chemin')
        table.add_column("Parametres")
        for route in rapport["routes"][:30]:
            table.add_row(route['methode'], route['chemin'], ', '.join(route['parametres']) or '-')
        console.print(table)

    if rapport['problemes']:
        table = Table(box=BX, border_style="yellow", header_style="bold yellow")
        table.add_column("Gravite", width=12)
        table.add_column('Element')
        table.add_column("Message")
        for probleme in rapport["problemes"][:30]:
            table.add_row(probleme['gravite'], probleme['element'], probleme['message'])
        console.print(table)
    else:
        ok('Aucune incoherence structurelle detectee.')

    valides = sum(1 for cas in rapport["cas_de_test"] if cas["valide"])
    console.print(f"[bold]Cas de test :[/] {len(rapport["cas_de_test"])} "
                  f"({valides} valides, {len(rapport['cas_de_test']) - valides} invalides)")

    if demander('Ecrire les fixtures JSON (oui/non)', 'oui').lower() in {'oui', 'o', 'y'}:
        destination=Path(demander("Fichier de sortie", "api-contract-cases.json")).expanduser()
        if destination.exists():
            warn('Le fichier existe deja : choisissez un autre nom.')
            return
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(json.dumps(rapport, ensure_ascii=False, indent=2) + "\n",
                                   encoding="utf-8")
        except OSError as exc:
            warn(f"Ecriture impossible : {exc}")
            return
        console.print(Panel(f"{destination.resolve()}", title='Fixtures ecrites',
                            border_style=C_CYBER))
