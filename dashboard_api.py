import os
import json
import time
import sqlite3
import asyncio
import logging
import secrets
from pathlib import Path
from datetime import datetime
from collections import defaultdict

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "secop.db"

DASHBOARD_USER = os.getenv("DASHBOARD_USER") or ""
DASHBOARD_PASS = os.getenv("DASHBOARD_PASS") or ""
if not DASHBOARD_USER or not DASHBOARD_PASS:
    raise RuntimeError("Define DASHBOARD_USER y DASHBOARD_PASS en .env antes de iniciar el dashboard")

app = FastAPI(title="SECOP2 Dashboard API", version="1.0.0")
security = HTTPBasic()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rate limiting simple (60 req/min por IP) ──────────────────────────────────
_rate_store: dict = defaultdict(list)

def _check_rate(request: Request, limit: int = 60, window: int = 60):
    ip = request.client.host
    now = time.time()
    _rate_store[ip] = [t for t in _rate_store[ip] if now - t < window]
    if len(_rate_store[ip]) >= limit:
        raise HTTPException(status_code=429, detail="Demasiadas peticiones. Espera un momento.")
    _rate_store[ip].append(now)

def require_auth(credentials: HTTPBasicCredentials = Depends(security)):
    ok_user = secrets.compare_digest(credentials.username.encode(), DASHBOARD_USER.encode())
    ok_pass = secrets.compare_digest(credentials.password.encode(), DASHBOARD_PASS.encode())
    if not (ok_user and ok_pass):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas",
                            headers={"WWW-Authenticate": "Basic"})


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def row_to_dict(row) -> dict:
    return dict(row) if row else {}


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/api/stats")
def get_stats(request: Request, _=Depends(require_auth)):
    _check_rate(request)
    conn = get_conn()
    try:
        total = conn.execute("SELECT COUNT(*) FROM procesos").fetchone()[0]
        alertados = conn.execute("SELECT COUNT(*) FROM procesos WHERE alerted=1").fetchone()[0]
        docs_generados = conn.execute("SELECT COUNT(*) FROM procesos WHERE doc_generado=1").fetchone()[0]
        score_avg = conn.execute(
            "SELECT AVG(relevance_score) FROM procesos WHERE relevance_score > 0"
        ).fetchone()[0]

        por_categoria = conn.execute(
            "SELECT categoria, COUNT(*) as total, AVG(relevance_score) as score_avg "
            "FROM procesos GROUP BY categoria ORDER BY total DESC"
        ).fetchall()

        por_score = conn.execute(
            "SELECT "
            "SUM(CASE WHEN relevance_score >= 80 THEN 1 ELSE 0 END) as alta, "
            "SUM(CASE WHEN relevance_score >= 60 AND relevance_score < 80 THEN 1 ELSE 0 END) as media, "
            "SUM(CASE WHEN relevance_score < 60 AND relevance_score > 0 THEN 1 ELSE 0 END) as baja, "
            "SUM(CASE WHEN relevance_score = 0 THEN 1 ELSE 0 END) as sin_score "
            "FROM procesos"
        ).fetchone()

        last_run = conn.execute(
            "SELECT * FROM run_log ORDER BY id DESC LIMIT 1"
        ).fetchone()

        try:
            import cost_tracker
            costos = cost_tracker.get_cost_summary(conn)
        except Exception:
            costos = {}

        return {
            "total": total,
            "alertados": alertados,
            "docs_generados": docs_generados,
            "score_promedio": round(score_avg, 1) if score_avg else 0,
            "por_categoria": [row_to_dict(r) for r in por_categoria],
            "por_score": row_to_dict(por_score) if por_score else {},
            "ultimo_run": row_to_dict(last_run) if last_run else None,
            "costos": costos,
        }
    finally:
        conn.close()


@app.get("/api/procesos")
def get_procesos(request: Request, _=Depends(require_auth),
    categoria: str = None,
    min_score: int = 0,
    alerted: int = None,
    doc_generado: int = None,
    busqueda: str = None,
    limit: int = 100,
    offset: int = 0,
):
    conn = get_conn()
    try:
        conditions = ["1=1"]
        params = []

        if categoria:
            conditions.append("categoria = ?")
            params.append(categoria)
        if min_score:
            conditions.append("relevance_score >= ?")
            params.append(min_score)
        if alerted is not None:
            conditions.append("alerted = ?")
            params.append(alerted)
        if doc_generado is not None:
            conditions.append("doc_generado = ?")
            params.append(doc_generado)
        if busqueda:
            conditions.append(
                "(nombre_proceso LIKE ? OR entidad LIKE ? OR ciudad LIKE ?)"
            )
            term = f"%{busqueda}%"
            params.extend([term, term, term])

        where = " AND ".join(conditions)
        total = conn.execute(
            f"SELECT COUNT(*) FROM procesos WHERE {where}", params
        ).fetchone()[0]

        rows = conn.execute(
            f"SELECT id_proceso, nombre_proceso, entidad, modalidad, estado, "
            f"valor_proceso, fecha_publicacion, departamento, ciudad, categoria, "
            f"relevance_score, justificacion, url_secop, fecha_scraped, alerted, doc_generado "
            f"FROM procesos WHERE {where} "
            f"ORDER BY relevance_score DESC, fecha_scraped DESC "
            f"LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()

        return {
            "total": total,
            "items": [row_to_dict(r) for r in rows],
            "limit": limit,
            "offset": offset,
        }
    finally:
        conn.close()


@app.get("/api/procesos/{id_proceso}")
def get_proceso(id_proceso: str, request: Request, _=Depends(require_auth)):
    _check_rate(request)
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM procesos WHERE id_proceso = ?", (id_proceso,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Proceso no encontrado")
        data = row_to_dict(row)
        if data.get("raw_json"):
            try:
                data["raw_json"] = json.loads(data["raw_json"])
            except Exception:
                pass
        return data
    finally:
        conn.close()


@app.get("/api/runs")
def get_runs(limit: int = 20, request: Request = None, _=Depends(require_auth)):
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM run_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [row_to_dict(r) for r in rows]
    finally:
        conn.close()


@app.post("/api/buscar")
def trigger_busqueda(dias: int = 7, _=Depends(require_auth)):
    """Crea una orden en la DB para que el bot ejecute la búsqueda."""
    import db_manager
    conn = get_conn()
    try:
        if db_manager.has_running_order(conn):
            return {"status": "en_curso", "message": "Ya hay una búsqueda en progreso"}
        dias = max(1, min(int(dias), 60))
        order_id = db_manager.create_order(conn, "buscar", f"dias={dias}")
        return {"status": "iniciada", "order_id": order_id,
                "message": f"Búsqueda solicitada — últimos {dias} días"}
    finally:
        conn.close()


@app.get("/api/buscar/estado")
def estado_busqueda(_=Depends(require_auth)):
    import db_manager
    conn = get_conn()
    try:
        return {"en_curso": db_manager.has_running_order(conn)}
    finally:
        conn.close()


@app.post("/api/generar/{id_proceso}")
def generar_documento(id_proceso: str, _=Depends(require_auth)):
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM procesos WHERE id_proceso = ?", (id_proceso,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Proceso no encontrado")
        proc = row_to_dict(row)
    finally:
        conn.close()

    try:
        from doc_generator import generate_doc
        raw = json.loads(proc.get("raw_json") or "{}")
        output_path = generate_doc(proc, raw)
    except Exception as e:
        log.error("Error generando doc: %s", e)
        raise HTTPException(status_code=500, detail=f"Error generando documento: {e}")

    conn2 = get_conn()
    try:
        conn2.execute(
            "UPDATE procesos SET doc_generado=1 WHERE id_proceso=?", (id_proceso,)
        )
        conn2.commit()
    finally:
        conn2.close()

    return FileResponse(
        path=output_path,
        filename=Path(output_path).name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("dashboard_api:app", host="0.0.0.0", port=8000, reload=True)
