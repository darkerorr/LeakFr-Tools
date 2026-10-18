"""Dossiers d'investigation OSINT - stocke via SQLite.

Chaque dossier (case) contient :
  - Titre, description, date de creation/modification
  - Notes (observations, hypotheses, conclusions)
  - Sources collectees avec metadonnees
Les mots de passe, jetons et secrets personnels ne sont jamais stockes.
"""
import hashlib
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from core.config import CASES_DB, HISTORY_FILE, DATA_DIR



def _connect():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn =sqlite3.connect(CASES_DB, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _init_db():
    conn=_connect()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS cases (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL,
            description TEXT DEFAULT '',
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS notes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id     INTEGER NOT NULL,
            kind        TEXT NOT NULL DEFAULT 'observation',
            content     TEXT NOT NULL DEFAULT '',
            created_at  TEXT NOT NULL,
            FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS evidence (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id       INTEGER NOT NULL,
            path          TEXT NOT NULL,
            sha256        TEXT NOT NULL,
            size          INTEGER NOT NULL DEFAULT 0,
            source        TEXT DEFAULT '',
            note          TEXT DEFAULT '',
            recorded_at   TEXT NOT NULL,
            previous_hash TEXT DEFAULT '',
            entry_hash    TEXT NOT NULL,
            FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS evidence_checks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            evidence_id INTEGER NOT NULL,
            checked_at  TEXT NOT NULL,
            intact      INTEGER NOT NULL,
            motif       TEXT DEFAULT '',
            sha256      TEXT DEFAULT '',
            FOREIGN KEY (evidence_id) REFERENCES evidence(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS sources (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id     INTEGER NOT NULL,
            data_type   TEXT DEFAULT '',
            value       TEXT DEFAULT '',
            tool_name   TEXT DEFAULT '',
            source_url  TEXT DEFAULT '',
            collected_at TEXT NOT NULL,
            errors      TEXT DEFAULT '',
            verification TEXT DEFAULT 'non_verifie',
            user_note   TEXT DEFAULT '',
            FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE
        );
    """)
    conn.commit()
    conn.close()



def lister_cases() -> list:
    """Retourne tous les dossiers tries par date de modification."""
    _init_db()
    conn =_connect()
    rows= conn.execute('SELECT * FROM cases ORDER BY updated_at DESC').fetchall()
    conn.close()
    return [dict(r) for r in rows]


def creer_case(title: str, description:str= "") -> int:
    """Cree un dossier et retourne son ID."""
    _init_db()
    now =datetime.now(timezone.utc).isoformat()
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO cases (title, description, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (title.strip(), description.strip(), now, now),
    )
    conn.commit()
    case_id = cur.lastrowid
    conn.close()
    _ajouter_historique("creer_case", {"id": case_id, "title": title})
    return case_id


def obtenir_case(case_id:int):
    """Retourne un dossier avec ses notes et sources."""
    _init_db()
    conn = _connect()
    case= conn.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
    if not case:
        conn.close()
        return None
    case = dict(case)
    case['notes'] =[dict(r) for r in conn.execute('SELECT * FROM notes WHERE case_id=? ORDER BY created_at', (case_id,)).fetchall()]
    case["sources"]= [dict(r) for r in conn.execute("SELECT * FROM sources WHERE case_id=? ORDER BY collected_at", (case_id,)).fetchall()]
    conn.close()
    return case


def renommer_case(case_id: int, title: str) -> bool:
    """Renomme un dossier."""
    now = datetime.now(timezone.utc).isoformat()
    conn =_connect()
    conn.execute("UPDATE cases SET title=?, updated_at=? WHERE id=?", (title.strip(), now, case_id))
    conn.commit()
    ok = conn.total_changes > 0
    conn.close()
    if ok:
        _ajouter_historique('renommer_case', {'id': case_id, 'title':title})
    return ok


def supprimer_case(case_id: int) -> bool:
    """Supprime un dossier et tout son contenu."""
    conn =_connect()
    conn.execute("DELETE FROM cases WHERE id=?", (case_id,))
    conn.commit()
    ok = conn.total_changes > 0
    conn.close()
    if ok:
        _ajouter_historique('supprimer_case', {'id': case_id})
    return ok



VALID_KINDS = ("observation", "hypothese", "conclusion", "note_libre")


def ajouter_note(case_id: int, kind: str, content: str) -> int:
    """Ajoute une note a un dossier. kind doit etre dans VALID_KINDS."""
    if kind not in VALID_KINDS:
        kind ="note_libre"
    now =datetime.now(timezone.utc).isoformat()
    conn = _connect()
    cur= conn.execute(
        'INSERT INTO notes (case_id, kind, content, created_at) VALUES (?, ?, ?, ?)',
        (case_id, kind, content.strip(), now),
    )
    conn.commit()
    note_id = cur.lastrowid
    conn.close()
    conn = _connect()
    conn.execute("UPDATE cases SET updated_at=? WHERE id=?", (now, case_id))
    conn.commit()
    conn.close()
    return note_id


def modifier_note(note_id: int, content: str) -> bool:
    """Modifie le contenu d'une note."""
    conn= _connect()
    conn.execute("UPDATE notes SET content=? WHERE id=?", (content.strip(), note_id))
    conn.commit()
    ok=conn.total_changes > 0
    conn.close()
    return ok


def supprimer_note(note_id:int) -> bool:
    """Supprime une note."""
    conn= _connect()
    conn.execute("DELETE FROM notes WHERE id=?", (note_id,))
    conn.commit()
    ok= conn.total_changes > 0
    conn.close()
    return ok



def ajouter_source(case_id: int, data_type: str ="", value: str = "",
                   tool_name: str = "", source_url: str = "",
                   errors: str = '', verification: str = 'non_verifie',
                   user_note:str= ""):
    """Ajoute une source collectee a un dossier."""
    now = datetime.now(timezone.utc).isoformat()
    conn = _connect()
    cur= conn.execute(
        'INSERT INTO sources (case_id, data_type, value, tool_name, source_url, collected_at, errors, verification, user_note) '
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (case_id, data_type, value, tool_name, source_url, now, errors, verification, user_note),
    )
    conn.commit()
    source_id= cur.lastrowid
    conn.close()
    conn =_connect()
    conn.execute("UPDATE cases SET updated_at=? WHERE id=?", (now, case_id))
    conn.commit()
    conn.close()
    return source_id


def modifier_source(source_id: int, **kwargs):
    """Modifie les champs donnes d'une source."""
    fields = {k: v for k, v in kwargs.items() if k in ("user_note", "verification", "value")}
    if not fields:
        return False
    sets =", ".join(f"{k}=?" for k in fields)
    vals= list(fields.values()) + [source_id]
    conn = _connect()
    conn.execute(f"UPDATE sources SET {sets} WHERE id=?", vals)
    conn.commit()
    ok = conn.total_changes > 0
    conn.close()
    return ok


def supprimer_source(source_id: int) -> bool:
    conn= _connect()
    conn.execute("DELETE FROM sources WHERE id=?", (source_id,))
    conn.commit()
    ok=conn.total_changes > 0
    conn.close()
    return ok



def _ajouter_historique(action:str, details: dict):
    """Ajoute une entree dans l'historique (fichier JSON)."""
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        if os.path.isfile(HISTORY_FILE):
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                hist = json.load(f)
        else:
            hist = []
    except (json.JSONDecodeError, OSError):
        hist = []

    if not isinstance(hist, list):
        hist =[]

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        'details': details,
    }
    hist.append(entry)

    max_hist= 500
    if len(hist) > max_hist:
        hist = hist[-max_hist:]

    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(hist, f, indent=2, ensure_ascii=False)
    except OSError:
        pass


def charger_historique(limit:int= 50) -> list:
    """Charge les dernieres entrees de l'historique."""
    if not os.path.isfile(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            hist = json.load(f)
        if not isinstance(hist, list):
            return []
        return hist[-limit:]
    except (json.JSONDecodeError, OSError):
        return []


def effacer_historique():
    """Supprime tout l'historique."""
    try:
        if os.path.isfile(HISTORY_FILE):
            os.remove(HISTORY_FILE)
        return True
    except OSError:
        return False



def _sha256_fichier(chemin):
    digest = hashlib.sha256()
    with open(chemin, 'rb') as flux:
        for bloc in iter(lambda: flux.read(1 << 20), b""):
            digest.update(bloc)
    return digest.hexdigest()


def _empreinte_entree(precedent, champs):
    graine= precedent + "\n" + "\n".join(f"{cle}={champs[cle]}" for cle in sorted(champs))
    return hashlib.sha256(graine.encode("utf-8")).hexdigest()


def ajouter_preuve(case_id, path, source="", note=""):
    """Enregistre un fichier local dans le registre chaine du dossier.

    Le fichier n'est jamais modifie ; seule son empreinte est stockee.
    """
    _init_db()
    chemin= Path(path).expanduser().resolve()
    if not chemin.is_file():
        raise ValueError(f"fichier introuvable : {chemin}")
    empreinte= _sha256_fichier(chemin)
    taille = chemin.stat().st_size
    horodatage = datetime.now(timezone.utc).isoformat()
    champs = {
        'case_id':str(case_id), 'path': str(chemin), 'sha256':empreinte,
        "size": str(taille), "source": source.strip(), "note": note.strip(),
        "recorded_at": horodatage,
    }
    conn = _connect()
    dernier = conn.execute(
        'SELECT entry_hash FROM evidence WHERE case_id=? ORDER BY id DESC LIMIT 1',
        (case_id,),
    ).fetchone()
    precedent =dernier['entry_hash'] if dernier else ''
    champs["previous_hash"]= precedent
    entree = _empreinte_entree(precedent, champs)
    cur = conn.execute(
        "INSERT INTO evidence (case_id, path, sha256, size, source, note, recorded_at, "
        "previous_hash, entry_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (case_id, str(chemin), empreinte, taille, champs['source'], champs['note'],
         horodatage, precedent, entree),
    )
    conn.execute('UPDATE cases SET updated_at=? WHERE id=?', (horodatage, case_id))
    conn.commit()
    preuve_id = cur.lastrowid
    conn.close()
    _ajouter_historique("ajouter_preuve", {"case":case_id, "preuve": preuve_id})
    return preuve_id


def lister_preuves(case_id):
    """Liste les preuves d'un dossier dans l'ordre du registre."""
    _init_db()
    conn = _connect()
    rows =conn.execute(
        "SELECT * FROM evidence WHERE case_id=? ORDER BY id", (case_id,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def verifier_preuve(evidence_id):
    """Recalcule l'empreinte du fichier, compare et journalise le controle."""
    _init_db()
    conn = _connect()
    row = conn.execute("SELECT * FROM evidence WHERE id=?", (evidence_id,)).fetchone()
    if not row:
        conn.close()
        raise ValueError(f"preuve inconnue : {evidence_id}")
    preuve = dict(row)
    chemin = Path(preuve["path"])
    actuel = _sha256_fichier(chemin) if chemin.is_file() else None
    if actuel is None:
        motif ="fichier absent"
    elif actuel ==preuve["sha256"]:
        motif= 'empreinte identique'
    else:
        motif ="empreinte differente : le fichier a change"
    resultat ={
        "id":evidence_id,
        "intact": actuel == preuve["sha256"],
        'motif': motif,
        "attendu": preuve["sha256"],
        "actuel":actuel,
    }
    conn.execute(
        "INSERT INTO evidence_checks (evidence_id, checked_at, intact, motif, sha256) "
        'VALUES (?, ?, ?, ?, ?)',
        (evidence_id, datetime.now(timezone.utc).isoformat(), int(resultat["intact"]),
         motif, actuel or ""),
    )
    conn.commit()
    conn.close()
    return resultat


def lister_verifications(evidence_id=None, case_id=None, limite=200):
    """Retourne l'historique des controles, filtre par preuve ou par dossier."""
    _init_db()
    conn = _connect()
    if evidence_id is not None:
        rows = conn.execute(
            'SELECT * FROM evidence_checks WHERE evidence_id=? ORDER BY id DESC LIMIT ?',
            (evidence_id, limite),
        ).fetchall()
    elif case_id is not None:
        rows =conn.execute(
            "SELECT c.* FROM evidence_checks c JOIN evidence e ON e.id = c.evidence_id "
            'WHERE e.case_id=? ORDER BY c.id DESC LIMIT ?',
            (case_id, limite),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM evidence_checks ORDER BY id DESC LIMIT ?", (limite,)
        ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def verifier_chaine(case_id):
    """Verifie la continuite des empreintes du registre.

    Une modification locale est detectable, mais un acteur qui reecrit tout le
    registre et recalcule les empreintes n'est pas detectable : il faut conserver
    une copie externe de la tete de chaine pour cela.
    """
    _init_db()
    preuves =lister_preuves(case_id)
    anomalies = []
    precedent =''
    for preuve in preuves:
        champs= {
            'case_id': str(preuve['case_id']), 'path': preuve['path'],
            "sha256": preuve["sha256"], "size":str(preuve["size"]),
            "source": preuve["source"], "note": preuve["note"],
            'recorded_at': preuve['recorded_at'],
            "previous_hash": preuve["previous_hash"],
        }
        attendu = _empreinte_entree(precedent, champs)
        if preuve["previous_hash"] !=precedent:
            anomalies.append({"id": preuve["id"], "motif": "maillon precedent inattendu"})
        if attendu != preuve['entry_hash']:
            anomalies.append({"id": preuve["id"], "motif": "empreinte d'entree incoherente"})
        precedent = preuve["entry_hash"]
    return {'valide': not anomalies, 'entrees': len(preuves), 'anomalies': anomalies,
            "tete":precedent or None}


def exporter_preuves_json(case_id):
    """Retourne le registre et l'etat de verification d'un dossier."""
    return {
        "case_id": case_id,
        "registre": lister_preuves(case_id),
        'chaine':verifier_chaine(case_id),
        "verifications": lister_verifications(case_id=case_id),
    }


def exporter_preuves_markdown(case_id):
    """Rend le registre lisible, avec ses limites explicites."""
    preuves = lister_preuves(case_id)
    chaine = verifier_chaine(case_id)
    lignes= [f"# Registre de preuves du dossier {case_id}", '']
    lignes.append("| # | Fichier | SHA-256 | Taille | Enregistre le | Source |")
    lignes.append("|---|---|---|---|---|---|")
    for preuve in preuves:
        lignes.append(
            f"| {preuve['id']} | {preuve['path']} | {preuve['sha256'][:16]}… | "
            f"{preuve["size"]} | {preuve["recorded_at"]} | {preuve["source"] or "-"} |"
        )
    lignes.extend(["", "## Verification", ""])
    lignes.append(f"- Entrees : {chaine["entrees"]}")
    lignes.append(f"- Chaine : {'intacte' if chaine['valide'] else 'incoherente'}")
    lignes.append(f"- Tete de chaine : {chaine['tete'] or '-'}")
    for anomalie in chaine['anomalies']:
        lignes.append(f"- Anomalie entree {anomalie['id']} : {anomalie['motif']}")
    controles = lister_verifications(case_id=case_id)
    lignes.extend(['', '## Historique des verifications', ''])
    if not controles:
        lignes.append("Aucun controle enregistre.")
    else:
        lignes.append("| Preuve | Controle (UTC) | Etat | Detail |")
        lignes.append("|---|---|---|---|")
        for controle in controles[:50]:
            lignes.append(f"| {controle['evidence_id']} | {controle['checked_at']} | "
                          f"{'intact' if controle['intact'] else 'modifie'} | {controle['motif']} |")
    lignes.extend(['', '## Limites', ''])
    lignes.append("Ce registre est local et detecte une modification accidentelle ou "
                  "isolee des entrees. Il ne rend pas les fichiers immuables : un acteur "
                  "qui reecrit le registre et recalcule les empreintes n'est pas detectable "
                  "sans une copie externe de la tete de chaine.")
    return "\n".join(lignes) + "\n"



def exporter_case_json(case_id: int) -> dict:
    """Retourne un dict JSON-serialisable d'un dossier."""
    case= obtenir_case(case_id)
    if not case:
        return {"error": "Case not found"}
    return {
        'id':case['id'],
        "title": case["title"],
        "description": case["description"],
        'created_at':case['created_at'],
        "updated_at": case["updated_at"],
        "notes": case["notes"],
        'sources': case['sources'],
        "evidence": lister_preuves(case_id),
    }


def exporter_tout_json() -> list:
    """Exporte tous les dossiers en une liste JSON."""
    cases =lister_cases()
    return [exporter_case_json(c["id"]) for c in cases]



_init_db()