"""Dossiers d'investigation OSINT - stocke via SQLite.

Chaque dossier (case) contient :
  - Titre, description, date de creation/modification
  - Notes (observations, hypotheses, conclusions)
  - Sources collectees avec metadonnees
Les mots de passe, jetons et secrets personnels ne sont jamais stockes.
"""
import json
import os
import sqlite3
import time
from datetime import datetime, timezone

from core.config import CASES_DB, HISTORY_FILE, DATA_DIR


# ---------------------------------------------------------------------------
# Base de donnees SQLite
# ---------------------------------------------------------------------------

def _connect():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(CASES_DB, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _init_db():
    conn = _connect()
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


# ---------------------------------------------------------------------------
# CRUD Dossiers
# ---------------------------------------------------------------------------

def lister_cases() -> list:
    """Retourne tous les dossiers tries par date de modification."""
    _init_db()
    conn = _connect()
    rows = conn.execute("SELECT * FROM cases ORDER BY updated_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def creer_case(title: str, description: str = "") -> int:
    """Cree un dossier et retourne son ID."""
    _init_db()
    now = datetime.now(timezone.utc).isoformat()
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


def obtenir_case(case_id: int):
    """Retourne un dossier avec ses notes et sources."""
    _init_db()
    conn = _connect()
    case = conn.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
    if not case:
        conn.close()
        return None
    case = dict(case)
    case["notes"] = [dict(r) for r in conn.execute("SELECT * FROM notes WHERE case_id=? ORDER BY created_at", (case_id,)).fetchall()]
    case["sources"] = [dict(r) for r in conn.execute("SELECT * FROM sources WHERE case_id=? ORDER BY collected_at", (case_id,)).fetchall()]
    conn.close()
    return case


def renommer_case(case_id: int, title: str) -> bool:
    """Renomme un dossier."""
    now = datetime.now(timezone.utc).isoformat()
    conn = _connect()
    conn.execute("UPDATE cases SET title=?, updated_at=? WHERE id=?", (title.strip(), now, case_id))
    conn.commit()
    ok = conn.total_changes > 0
    conn.close()
    if ok:
        _ajouter_historique("renommer_case", {"id": case_id, "title": title})
    return ok


def supprimer_case(case_id: int) -> bool:
    """Supprime un dossier et tout son contenu."""
    conn = _connect()
    conn.execute("DELETE FROM cases WHERE id=?", (case_id,))
    conn.commit()
    ok = conn.total_changes > 0
    conn.close()
    if ok:
        _ajouter_historique("supprimer_case", {"id": case_id})
    return ok


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------

VALID_KINDS = ("observation", "hypothese", "conclusion", "note_libre")


def ajouter_note(case_id: int, kind: str, content: str) -> int:
    """Ajoute une note a un dossier. kind doit etre dans VALID_KINDS."""
    if kind not in VALID_KINDS:
        kind = "note_libre"
    now = datetime.now(timezone.utc).isoformat()
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO notes (case_id, kind, content, created_at) VALUES (?, ?, ?, ?)",
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
    conn = _connect()
    conn.execute("UPDATE notes SET content=? WHERE id=?", (content.strip(), note_id))
    conn.commit()
    ok = conn.total_changes > 0
    conn.close()
    return ok


def supprimer_note(note_id: int) -> bool:
    """Supprime une note."""
    conn = _connect()
    conn.execute("DELETE FROM notes WHERE id=?", (note_id,))
    conn.commit()
    ok = conn.total_changes > 0
    conn.close()
    return ok


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

def ajouter_source(case_id: int, data_type: str = "", value: str = "",
                   tool_name: str = "", source_url: str = "",
                   errors: str = "", verification: str = "non_verifie",
                   user_note: str = ""):
    """Ajoute une source collectee a un dossier."""
    now = datetime.now(timezone.utc).isoformat()
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO sources (case_id, data_type, value, tool_name, source_url, collected_at, errors, verification, user_note) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (case_id, data_type, value, tool_name, source_url, now, errors, verification, user_note),
    )
    conn.commit()
    source_id = cur.lastrowid
    conn.close()
    conn = _connect()
    conn.execute("UPDATE cases SET updated_at=? WHERE id=?", (now, case_id))
    conn.commit()
    conn.close()
    return source_id


def modifier_source(source_id: int, **kwargs):
    """Modifie les champs donnes d'une source."""
    fields = {k: v for k, v in kwargs.items() if k in ("user_note", "verification", "value")}
    if not fields:
        return False
    sets = ", ".join(f"{k}=?" for k in fields)
    vals = list(fields.values()) + [source_id]
    conn = _connect()
    conn.execute(f"UPDATE sources SET {sets} WHERE id=?", vals)
    conn.commit()
    ok = conn.total_changes > 0
    conn.close()
    return ok


def supprimer_source(source_id: int) -> bool:
    conn = _connect()
    conn.execute("DELETE FROM sources WHERE id=?", (source_id,))
    conn.commit()
    ok = conn.total_changes > 0
    conn.close()
    return ok


# ---------------------------------------------------------------------------
# Historique des operations
# ---------------------------------------------------------------------------

def _ajouter_historique(action: str, details: dict):
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
        hist = []

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "details": details,
    }
    hist.append(entry)

    max_hist = 500
    if len(hist) > max_hist:
        hist = hist[-max_hist:]

    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(hist, f, indent=2, ensure_ascii=False)
    except OSError:
        pass


def charger_historique(limit: int = 50) -> list:
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


# ---------------------------------------------------------------------------
# Export (appele par modules/export)
# ---------------------------------------------------------------------------

def exporter_case_json(case_id: int) -> dict:
    """Retourne un dict JSON-serialisable d'un dossier."""
    case = obtenir_case(case_id)
    if not case:
        return {"error": "Case not found"}
    return {
        "id": case["id"],
        "title": case["title"],
        "description": case["description"],
        "created_at": case["created_at"],
        "updated_at": case["updated_at"],
        "notes": case["notes"],
        "sources": case["sources"],
    }


def exporter_tout_json() -> list:
    """Exporte tous les dossiers en une liste JSON."""
    cases = lister_cases()
    return [exporter_case_json(c["id"]) for c in cases]


# ---------------------------------------------------------------------------
# Initialisation au chargement
# ---------------------------------------------------------------------------

_init_db()