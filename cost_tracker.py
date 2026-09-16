"""
Rastrea el consumo de tokens y costo diario de Claude.
Precios Mayo 2026: Haiku $0.80/$4 por 1M tokens. Sonnet $3/$15 por 1M tokens.
"""
import sqlite3
import threading
import logging
from datetime import date, datetime
from pathlib import Path

log = logging.getLogger(__name__)
_lock = threading.Lock()

PRICES = {
    "claude-haiku-4-5-20251001": {"input": 0.80 / 1_000_000, "output": 4.00 / 1_000_000},
    "claude-sonnet-4-6":         {"input": 3.00 / 1_000_000, "output": 15.00 / 1_000_000},
}

DAILY_CAP_USD = float(5.0)  # máximo $5/día — ajusta en .env si quieres


def _ensure_table(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_costs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp  TEXT,
            modelo     TEXT,
            operacion  TEXT,
            tokens_in  INTEGER,
            tokens_out INTEGER,
            costo_usd  REAL
        )
    """)
    conn.commit()


def register_usage(conn: sqlite3.Connection, modelo: str, operacion: str,
                   tokens_in: int, tokens_out: int) -> float:
    """Registra uso y retorna costo en USD de esta llamada."""
    precio = PRICES.get(modelo, {"input": 0, "output": 0})
    costo = (tokens_in * precio["input"]) + (tokens_out * precio["output"])
    with _lock:
        _ensure_table(conn)
        conn.execute(
            "INSERT INTO api_costs (timestamp, modelo, operacion, tokens_in, tokens_out, costo_usd) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (datetime.now().isoformat(), modelo, operacion, tokens_in, tokens_out, round(costo, 6))
        )
        conn.commit()
    log.info("Claude %s [%s] — in:%d out:%d — $%.4f", modelo.split("-")[1], operacion, tokens_in, tokens_out, costo)
    return costo


def get_daily_cost(conn: sqlite3.Connection) -> float:
    """Retorna el costo acumulado hoy en USD."""
    _ensure_table(conn)
    hoy = date.today().isoformat()
    row = conn.execute(
        "SELECT SUM(costo_usd) FROM api_costs WHERE timestamp LIKE ?",
        (f"{hoy}%",)
    ).fetchone()
    return round(row[0] or 0.0, 4)


def check_budget(conn: sqlite3.Connection, cap: float = None) -> tuple[bool, float]:
    """
    Verifica si hay presupuesto disponible hoy.
    Returns (puede_continuar: bool, gasto_hoy: float)
    """
    cap = cap or DAILY_CAP_USD
    gasto = get_daily_cost(conn)
    puede = gasto < cap
    if not puede:
        log.warning("PRESUPUESTO DIARIO AGOTADO — gastado: $%.3f / cap: $%.2f", gasto, cap)
    return puede, gasto


def get_cost_summary(conn: sqlite3.Connection) -> dict:
    """Resumen de costos para el dashboard."""
    _ensure_table(conn)
    hoy = date.today().isoformat()
    mes = hoy[:7]

    hoy_total = conn.execute(
        "SELECT SUM(costo_usd) FROM api_costs WHERE timestamp LIKE ?", (f"{hoy}%",)
    ).fetchone()[0] or 0

    mes_total = conn.execute(
        "SELECT SUM(costo_usd) FROM api_costs WHERE timestamp LIKE ?", (f"{mes}%",)
    ).fetchone()[0] or 0

    por_modelo = conn.execute(
        "SELECT modelo, SUM(costo_usd) as total, COUNT(*) as llamadas "
        "FROM api_costs WHERE timestamp LIKE ? GROUP BY modelo",
        (f"{hoy}%",)
    ).fetchall()

    return {
        "hoy_usd": round(hoy_total, 4),
        "mes_usd": round(mes_total, 4),
        "cap_diario_usd": DAILY_CAP_USD,
        "porcentaje_cap": round((hoy_total / DAILY_CAP_USD) * 100, 1),
        "por_modelo": [{"modelo": r[0].split("-")[1], "total": round(r[1], 4), "llamadas": r[2]}
                       for r in por_modelo],
    }
