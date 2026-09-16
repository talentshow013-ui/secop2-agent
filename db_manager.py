import sqlite3
import json
import threading
import logging
from datetime import datetime, timedelta

log = logging.getLogger(__name__)
_lock = threading.Lock()


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False, timeout=15.0)
    conn.row_factory = sqlite3.Row
    # WAL mode permite lectores y escritores simultáneos
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA foreign_keys=ON")
    except Exception as e:
        log.warning("No se pudieron aplicar PRAGMAs: %s", e)
    return conn


def init_db(db_path: str) -> sqlite3.Connection:
    conn = get_connection(db_path)
    with _lock:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS procesos (
                id_proceso       TEXT PRIMARY KEY,
                nombre_proceso   TEXT,
                entidad          TEXT,
                modalidad        TEXT,
                estado           TEXT,
                valor_proceso    TEXT,
                fecha_publicacion TEXT,
                departamento     TEXT,
                ciudad           TEXT,
                categoria        TEXT,
                relevance_score  INTEGER DEFAULT 0,
                justificacion    TEXT,
                url_secop        TEXT,
                raw_json         TEXT,
                fecha_scraped    TEXT,
                alerted          INTEGER DEFAULT 0,
                doc_generado     INTEGER DEFAULT 0,
                fecha_cierre     TEXT,
                cierre_alertado  INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS run_log (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp            TEXT,
                procesos_fetched     INTEGER,
                procesos_nuevos      INTEGER,
                procesos_alertados   INTEGER,
                duracion_segundos    REAL,
                error                TEXT
            );

            CREATE TABLE IF NOT EXISTS conversaciones (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id     INTEGER NOT NULL,
                role        TEXT NOT NULL,
                content     TEXT NOT NULL,
                timestamp   TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_conv_chat ON conversaciones(chat_id);

            CREATE TABLE IF NOT EXISTS memory_summary (
                chat_id     INTEGER PRIMARY KEY,
                resumen     TEXT,
                msg_count   INTEGER DEFAULT 0,
                timestamp   TEXT
            );

            CREATE TABLE IF NOT EXISTS hechos (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id     INTEGER NOT NULL,
                hecho       TEXT NOT NULL,
                categoria   TEXT,
                importancia INTEGER DEFAULT 1,
                timestamp   TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_hechos_chat ON hechos(chat_id, importancia DESC);

            CREATE TABLE IF NOT EXISTS proceso_contexto (
                chat_id     INTEGER PRIMARY KEY,
                id_proceso  TEXT,
                url_proceso TEXT,
                nombre      TEXT,
                entidad     TEXT,
                texto_docs  TEXT,
                timestamp   TEXT
            );

            CREATE TABLE IF NOT EXISTS api_orders (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                accion      TEXT NOT NULL,
                params      TEXT,
                estado      TEXT DEFAULT 'pendiente',
                timestamp   TEXT NOT NULL,
                completado  TEXT
            );
        """)
        conn.commit()

    # Migraciones — agrega columnas nuevas si no existen
    _migrate(conn)

    log.info("Base de datos inicializada en %s", db_path)
    return conn


def _migrate(conn: sqlite3.Connection):
    """Aplica migraciones de schema sin borrar datos."""
    migrations = [
        "ALTER TABLE procesos ADD COLUMN fecha_cierre TEXT",
        "ALTER TABLE procesos ADD COLUMN cierre_alertado INTEGER DEFAULT 0",
        "CREATE TABLE IF NOT EXISTS proceso_contexto (chat_id INTEGER PRIMARY KEY, id_proceso TEXT, url_proceso TEXT, nombre TEXT, entidad TEXT, texto_docs TEXT, timestamp TEXT)",
        "CREATE TABLE IF NOT EXISTS memory_summary (chat_id INTEGER PRIMARY KEY, resumen TEXT, msg_count INTEGER DEFAULT 0, timestamp TEXT)",
        "CREATE TABLE IF NOT EXISTS hechos (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER NOT NULL, hecho TEXT NOT NULL, categoria TEXT, importancia INTEGER DEFAULT 1, timestamp TEXT)",
        "CREATE INDEX IF NOT EXISTS idx_hechos_chat ON hechos(chat_id, importancia DESC)",
    ]
    for sql in migrations:
        try:
            conn.execute(sql)
            conn.commit()
            log.info("Migración aplicada: %s", sql[:60])
        except sqlite3.OperationalError:
            pass  # columna ya existe


def is_new(conn: sqlite3.Connection, id_proceso: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM procesos WHERE id_proceso = ?", (id_proceso,)
    ).fetchone()
    return row is None


def insert_proceso(conn: sqlite3.Connection, proc: dict) -> None:
    with _lock:
        conn.execute("""
            INSERT OR IGNORE INTO procesos (
                id_proceso, nombre_proceso, entidad, modalidad, estado,
                valor_proceso, fecha_publicacion, departamento, ciudad,
                categoria, relevance_score, justificacion, url_secop,
                raw_json, fecha_scraped, alerted, fecha_cierre
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
        """, (
            proc.get("id_proceso", ""),
            proc.get("nombre_proceso", ""),
            proc.get("entidad", ""),
            proc.get("modalidad", ""),
            proc.get("estado", ""),
            str(proc.get("valor_proceso", "")),
            proc.get("fecha_publicacion", ""),
            proc.get("departamento", ""),
            proc.get("ciudad", ""),
            proc.get("categoria", "otro"),
            proc.get("_score", 0),
            proc.get("_justificacion", ""),
            proc.get("url_secop", ""),
            json.dumps(proc, ensure_ascii=False),
            datetime.now().isoformat(),
            proc.get("fecha_cierre", ""),
        ))
        conn.commit()


def mark_alerted(conn: sqlite3.Connection, id_proceso: str) -> None:
    with _lock:
        conn.execute(
            "UPDATE procesos SET alerted = 1 WHERE id_proceso = ?", (id_proceso,)
        )
        conn.commit()


def mark_doc_generado(conn: sqlite3.Connection, id_proceso: str) -> None:
    with _lock:
        conn.execute(
            "UPDATE procesos SET doc_generado = 1 WHERE id_proceso = ?", (id_proceso,)
        )
        conn.commit()


def get_unalerted(conn: sqlite3.Connection, min_score: int = 60):
    return conn.execute(
        "SELECT * FROM procesos WHERE alerted = 0 AND relevance_score >= ? ORDER BY relevance_score DESC",
        (min_score,)
    ).fetchall()


def get_recent_alerted(conn: sqlite3.Connection, limit: int = 5):
    return conn.execute(
        "SELECT * FROM procesos WHERE alerted = 1 ORDER BY fecha_scraped DESC LIMIT ?",
        (limit,)
    ).fetchall()


def get_process_by_id(conn: sqlite3.Connection, id_proceso: str):
    return conn.execute(
        "SELECT * FROM procesos WHERE id_proceso = ?", (id_proceso,)
    ).fetchone()


def log_run(conn: sqlite3.Connection, stats: dict) -> None:
    with _lock:
        conn.execute("""
            INSERT INTO run_log (timestamp, procesos_fetched, procesos_nuevos,
                                 procesos_alertados, duracion_segundos, error)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            stats.get("fetched", 0),
            stats.get("nuevos", 0),
            stats.get("alertados", 0),
            stats.get("duracion", 0),
            stats.get("error"),
        ))
        conn.commit()


def get_last_run(conn: sqlite3.Connection):
    row = conn.execute(
        "SELECT * FROM run_log ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return dict(row) if row else {}


def count_processes(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM procesos").fetchone()[0]


def delete_hecho_like(conn: sqlite3.Connection, chat_id: int, texto: str) -> int:
    """Borra hechos que contengan el texto dado. Retorna cantidad borrada."""
    with _lock:
        cur = conn.execute(
            "DELETE FROM hechos WHERE chat_id=? AND lower(hecho) LIKE lower(?)",
            (chat_id, f"%{texto}%")
        )
        conn.commit()
    return cur.rowcount


def save_hecho(conn: sqlite3.Connection, chat_id: int, hecho: str, categoria: str, importancia: int = 1):
    with _lock:
        # Evita duplicados exactos
        existe = conn.execute(
            "SELECT 1 FROM hechos WHERE chat_id=? AND hecho=?", (chat_id, hecho)
        ).fetchone()
        if not existe:
            conn.execute(
                "INSERT INTO hechos (chat_id, hecho, categoria, importancia, timestamp) VALUES (?,?,?,?,?)",
                (chat_id, hecho, categoria, importancia, datetime.now().isoformat())
            )
            conn.commit()


def get_hechos_relevantes(conn: sqlite3.Connection, chat_id: int, limite: int = 10) -> list:
    """Retorna los hechos más importantes del usuario."""
    rows = conn.execute(
        "SELECT hecho, categoria, importancia FROM hechos WHERE chat_id=? "
        "ORDER BY importancia DESC, timestamp DESC LIMIT ?",
        (chat_id, limite)
    ).fetchall()
    return [dict(r) for r in rows]


def get_hechos_por_categoria(conn: sqlite3.Connection, chat_id: int, categoria: str) -> list:
    rows = conn.execute(
        "SELECT hecho FROM hechos WHERE chat_id=? AND categoria=? ORDER BY importancia DESC LIMIT 5",
        (chat_id, categoria)
    ).fetchall()
    return [r["hecho"] for r in rows]


def get_memory_summary(conn: sqlite3.Connection, chat_id: int) -> dict:
    row = conn.execute(
        "SELECT * FROM memory_summary WHERE chat_id = ?", (chat_id,)
    ).fetchone()
    return dict(row) if row else {}


def save_memory_summary(conn: sqlite3.Connection, chat_id: int, resumen: str, msg_count: int):
    with _lock:
        conn.execute("""
            INSERT OR REPLACE INTO memory_summary (chat_id, resumen, msg_count, timestamp)
            VALUES (?, ?, ?, ?)
        """, (chat_id, resumen, msg_count, datetime.now().isoformat()))
        conn.commit()


def count_messages(conn: sqlite3.Connection, chat_id: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM conversaciones WHERE chat_id = ?", (chat_id,)
    ).fetchone()
    return row[0] if row else 0


def save_proceso_contexto(conn: sqlite3.Connection, chat_id: int, proceso: dict, texto_docs: str):
    with _lock:
        conn.execute("""
            INSERT OR REPLACE INTO proceso_contexto
            (chat_id, id_proceso, url_proceso, nombre, entidad, texto_docs, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            chat_id,
            proceso.get("id_proceso", ""),
            proceso.get("url_secop", ""),
            proceso.get("nombre_proceso", ""),
            proceso.get("entidad", ""),
            texto_docs,
            datetime.now().isoformat(),
        ))
        conn.commit()


def get_proceso_contexto(conn: sqlite3.Connection, chat_id: int) -> dict:
    row = conn.execute(
        "SELECT * FROM proceso_contexto WHERE chat_id = ?", (chat_id,)
    ).fetchone()
    return dict(row) if row else {}


def clear_proceso_contexto(conn: sqlite3.Connection, chat_id: int):
    with _lock:
        conn.execute("DELETE FROM proceso_contexto WHERE chat_id = ?", (chat_id,))
        conn.commit()


def create_order(conn: sqlite3.Connection, accion: str, params: str = "") -> int:
    with _lock:
        cur = conn.execute(
            "INSERT INTO api_orders (accion, params, estado, timestamp) VALUES (?, ?, 'pendiente', ?)",
            (accion, params, datetime.now().isoformat())
        )
        conn.commit()
        return cur.lastrowid


def get_pending_orders(conn: sqlite3.Connection):
    return conn.execute(
        "SELECT * FROM api_orders WHERE estado = 'pendiente' ORDER BY id ASC"
    ).fetchall()


def mark_order_done(conn: sqlite3.Connection, order_id: int, estado: str = "completado"):
    with _lock:
        conn.execute(
            "UPDATE api_orders SET estado = ?, completado = ? WHERE id = ?",
            (estado, datetime.now().isoformat(), order_id)
        )
        conn.commit()


def has_running_order(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM api_orders WHERE estado IN ('pendiente', 'ejecutando') LIMIT 1"
    ).fetchone()
    return row is not None


def save_message(conn: sqlite3.Connection, chat_id: int, role: str, content: str) -> None:
    with _lock:
        conn.execute(
            "INSERT INTO conversaciones (chat_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (chat_id, role, content, datetime.now().isoformat())
        )
        conn.commit()


def get_history(conn: sqlite3.Connection, chat_id: int, limit: int = 20) -> list:
    rows = conn.execute(
        "SELECT role, content FROM conversaciones WHERE chat_id = ? "
        "ORDER BY id DESC LIMIT ?",
        (chat_id, limit)
    ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def clear_history(conn: sqlite3.Connection, chat_id: int) -> None:
    with _lock:
        conn.execute("DELETE FROM conversaciones WHERE chat_id = ?", (chat_id,))
        conn.commit()


def purge_old_conversations(conn: sqlite3.Connection, dias: int = 30) -> int:
    """Borra conversaciones más viejas que N días. Retorna cantidad borrada."""
    from datetime import timedelta
    limite = (datetime.now() - timedelta(days=dias)).isoformat()
    with _lock:
        cur = conn.execute("DELETE FROM conversaciones WHERE timestamp < ?", (limite,))
        conn.commit()
    return cur.rowcount


def purge_old_orders(conn: sqlite3.Connection, dias: int = 7) -> int:
    """Borra órdenes API completadas o con error más viejas que N días."""
    from datetime import timedelta
    limite = (datetime.now() - timedelta(days=dias)).isoformat()
    with _lock:
        cur = conn.execute(
            "DELETE FROM api_orders WHERE estado IN ('completado','error') AND timestamp < ?",
            (limite,)
        )
        conn.commit()
    return cur.rowcount


def get_ultimo_publicado(conn: sqlite3.Connection):
    return conn.execute(
        "SELECT * FROM procesos WHERE fecha_publicacion != '' "
        "ORDER BY fecha_publicacion DESC LIMIT 1"
    ).fetchone()


def get_procesos_hoy(conn: sqlite3.Connection):
    from datetime import date
    hoy = date.today().isoformat()
    return conn.execute(
        "SELECT * FROM procesos WHERE fecha_scraped LIKE ? ORDER BY relevance_score DESC",
        (f"{hoy}%",)
    ).fetchall()


def get_procesos_por_categoria(conn: sqlite3.Connection, categoria: str, limit: int = 5):
    return conn.execute(
        "SELECT * FROM procesos WHERE categoria = ? ORDER BY relevance_score DESC, fecha_scraped DESC LIMIT ?",
        (categoria, limit)
    ).fetchall()


def get_procesos_por_cerrar(conn: sqlite3.Connection, dias: int = 2) -> list:
    from datetime import date, timedelta
    hoy = date.today().isoformat()
    limite = (date.today() + timedelta(days=dias)).isoformat()
    return conn.execute(
        "SELECT * FROM procesos WHERE fecha_cierre != '' AND fecha_cierre IS NOT NULL "
        "AND fecha_cierre >= ? AND fecha_cierre <= ? AND cierre_alertado = 0 "
        "AND relevance_score >= 60 ORDER BY fecha_cierre ASC",
        (hoy, limite + "T23:59:59")
    ).fetchall()


def mark_cierre_alertado(conn: sqlite3.Connection, id_proceso: str) -> None:
    with _lock:
        conn.execute(
            "UPDATE procesos SET cierre_alertado=1 WHERE id_proceso=?", (id_proceso,)
        )
        conn.commit()


def get_resumen_db(conn: sqlite3.Connection) -> dict:
    total = conn.execute("SELECT COUNT(*) FROM procesos").fetchone()[0]
    relevantes = conn.execute("SELECT COUNT(*) FROM procesos WHERE relevance_score >= 60").fetchone()[0]
    ultimo = conn.execute(
        "SELECT nombre_proceso, entidad, ciudad, fecha_publicacion, relevance_score, categoria "
        "FROM procesos WHERE fecha_publicacion != '' ORDER BY fecha_publicacion DESC LIMIT 1"
    ).fetchone()
    por_cat = conn.execute(
        "SELECT categoria, COUNT(*) as n FROM procesos GROUP BY categoria ORDER BY n DESC"
    ).fetchall()
    return {
        "total": total,
        "relevantes": relevantes,
        "ultimo": dict(ultimo) if ultimo else None,
        "por_categoria": [dict(r) for r in por_cat],
    }
