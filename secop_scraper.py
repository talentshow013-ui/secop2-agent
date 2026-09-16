import time
import logging
import json
from datetime import datetime, timedelta
from sodapy import Socrata

log = logging.getLogger(__name__)

FIELD_ALIASES = {
    "id_proceso":        ["id_del_proceso", "referencia_del_proceso"],
    "nombre_proceso":    ["nombre_del_procedimiento", "nombre_del_proceso", "descripcion_del_proceso"],
    "entidad":           ["entidad", "nombre_entidad"],
    "nit_entidad":       ["nit_entidad"],
    "objeto":            ["descripci_n_del_procedimiento", "objeto_a_contratar", "nombre_del_procedimiento"],
    "modalidad":         ["modalidad_de_contratacion", "modalidad_contratacion"],
    "justificacion_modalidad": ["justificaci_n_modalidad_de"],
    "estado":            ["estado_del_procedimiento", "estado_de_apertura_del_proceso", "estado_resumen"],
    "estado_resumen":    ["estado_resumen"],
    "valor_proceso":     ["precio_base", "valor_del_proceso", "cuantia_proceso"],
    "fecha_publicacion": ["fecha_de_publicacion_del", "fecha_publicacion"],
    "fecha_ultima_publicacion": ["fecha_de_ultima_publicaci"],
    "departamento":      ["departamento_entidad", "departamento"],
    "ciudad":            ["ciudad_entidad", "ciudad_de_la_unidad_de", "ciudad"],
    "fase":              ["fase", "fase_del_proceso"],
    "url_proceso":       ["urlproceso"],
    "fecha_cierre":      ["fecha_de_publicacion_fase_3", "fecha_limite_de_recepcion"],
    "duracion":          ["duracion"],
    "unidad_duracion":   ["unidad_de_duracion"],
    "tipo_contrato":     ["tipo_de_contrato"],
    "subtipo_contrato":  ["subtipo_de_contrato"],
    "orden_entidad":     ["ordenentidad"],
    "codigo_categoria":  ["codigo_principal_de_categoria"],
    # Inteligencia competitiva
    "respuestas_ofertas":   ["conteo_de_respuestas_a_ofertas", "respuestas_al_procedimiento"],
    "proveedores_invitados": ["proveedores_invitados"],
    "proveedores_manifestaron": ["proveedores_que_manifestaron"],
    "visualizaciones":   ["visualizaciones_del"],
    # Datos de adjudicación (proceso ya cerrado)
    "adjudicado":        ["adjudicado"],
    "valor_adjudicacion": ["valor_total_adjudicacion"],
    "nit_ganador":       ["nit_del_proveedor_adjudicado"],
    "nombre_ganador":    ["nombre_del_proveedor"],
}


def _get_field(record: dict, field_key: str) -> str:
    for alias in FIELD_ALIASES.get(field_key, [field_key]):
        val = record.get(alias)
        if val is not None:
            return str(val).strip()
    return ""


def _build_where_clause(keywords: list, departamento: str, modalidad: str, estado: str, dias: int = 30) -> str:
    kw_conditions = []
    for kw in keywords:
        kw_esc = kw.replace("'", "''")
        kw_conditions.append(
            f"(upper(nombre_del_procedimiento) like upper('%{kw_esc}%') "
            f"OR upper(descripci_n_del_procedimiento) like upper('%{kw_esc}%'))"
        )
    kw_clause = " OR ".join(kw_conditions)

    dept_esc = departamento.replace("'", "''")
    mod_esc = modalidad.replace("'", "''")
    fecha_limite = (datetime.now() - timedelta(days=dias)).strftime("%Y-%m-%dT00:00:00")

    return (
        f"upper(departamento_entidad) like upper('%{dept_esc}%') "
        f"AND upper(modalidad_de_contratacion) like upper('%{mod_esc}%') "
        f"AND fecha_de_publicacion_del >= '{fecha_limite}' "
        f"AND ({kw_clause})"
    )


def _fetch_with_retry(client, dataset_id: str, where: str, page_size: int, offset: int, attempts: int = 3):
    last_exc = None
    for attempt in range(attempts):
        try:
            return client.get(
                dataset_id,
                where=where,
                limit=page_size,
                offset=offset,
                order="fecha_de_publicacion_del DESC",
                content_type="json",
            )
        except Exception as e:
            last_exc = e
            wait = 5 * (2 ** attempt)
            log.warning("Intento %d/%d falló: %s. Reintentando en %ds", attempt + 1, attempts, e, wait)
            time.sleep(wait)
    raise last_exc


def _fetch_all_pages(client, dataset_id: str, where: str, page_size: int = 1000) -> list:
    results = []
    offset = 0
    while True:
        page = _fetch_with_retry(client, dataset_id, where, page_size, offset)
        if not page:
            break
        results.extend(page)
        log.info("Página obtenida: %d registros (offset %d, total acumulado: %d)", len(page), offset, len(results))
        if len(page) < page_size:
            break
        offset += page_size
        if offset >= 50_000:
            log.warning("Límite de 50k registros de Socrata alcanzado")
            break
    return results


def _classify_category(text: str, categories: dict) -> str:
    text_lower = text.lower()
    best, best_count = "otro", 0
    for cat_key, cat_data in categories.items():
        count = sum(1 for kw in cat_data["keywords"] if kw.lower() in text_lower)
        if count > best_count:
            best_count = count
            best = cat_key
    return best


def _normalize(record: dict) -> dict:
    id_proceso = _get_field(record, "id_proceso")
    nombre = _get_field(record, "nombre_proceso")
    objeto = _get_field(record, "objeto")
    url = _get_field(record, "url_proceso") or (
        f"https://www.contratos.gov.co/consultas/detalleProceso.do"
        f"?numConstancia={id_proceso}"
    ) if id_proceso else ""
    # Limpia URL si viene como dict serializado
    if isinstance(url, str) and url.startswith("{"):
        import re as _re
        match = _re.search(r'https?://[^\s\'"}\]]+', url)
        url = match.group() if match else ""

    return {
        "id_proceso":        id_proceso,
        "nombre_proceso":    nombre,
        "entidad":           _get_field(record, "entidad"),
        "nit_entidad":       _get_field(record, "nit_entidad"),
        "objeto":            objeto,
        "modalidad":         _get_field(record, "modalidad"),
        "justificacion_modalidad": _get_field(record, "justificacion_modalidad"),
        "estado":            _get_field(record, "estado"),
        "estado_resumen":    _get_field(record, "estado_resumen"),
        "valor_proceso":     _get_field(record, "valor_proceso"),
        "fecha_publicacion": _get_field(record, "fecha_publicacion"),
        "fecha_ultima_publicacion": _get_field(record, "fecha_ultima_publicacion"),
        "departamento":      _get_field(record, "departamento"),
        "ciudad":            _get_field(record, "ciudad"),
        "fase":              _get_field(record, "fase"),
        "url_secop":         url,
        "fecha_cierre":      _get_field(record, "fecha_cierre"),
        # Contrato
        "duracion":          _get_field(record, "duracion"),
        "unidad_duracion":   _get_field(record, "unidad_duracion"),
        "tipo_contrato":     _get_field(record, "tipo_contrato"),
        "subtipo_contrato":  _get_field(record, "subtipo_contrato"),
        "orden_entidad":     _get_field(record, "orden_entidad"),
        "codigo_categoria":  _get_field(record, "codigo_categoria"),
        # Inteligencia competitiva
        "respuestas_ofertas": _get_field(record, "respuestas_ofertas"),
        "proveedores_invitados": _get_field(record, "proveedores_invitados"),
        "proveedores_manifestaron": _get_field(record, "proveedores_manifestaron"),
        "visualizaciones":   _get_field(record, "visualizaciones"),
        # Datos de adjudicación
        "adjudicado":        _get_field(record, "adjudicado"),
        "valor_adjudicacion": _get_field(record, "valor_adjudicacion"),
        "nit_ganador":       _get_field(record, "nit_ganador"),
        "nombre_ganador":    _get_field(record, "nombre_ganador"),
        "_raw":              record,
    }


def _filter_by_value(processes: list, valor_min: float = 0, valor_max: float = None) -> list:
    """Filtra procesos por rango de valor antes de enviarlos al scoring."""
    filtered = []
    for p in processes:
        val_raw = p.get("valor_proceso", "")
        try:
            val = float(val_raw) if val_raw else 0
        except (ValueError, TypeError):
            val = 0
        # Si no hay valor declarado, lo dejamos pasar (lo evalúa el scorer)
        if val == 0:
            filtered.append(p)
            continue
        if valor_min and val < valor_min:
            continue
        if valor_max and val > valor_max:
            continue
        filtered.append(p)
    return filtered


def run_scrape(config: dict, app_token: str, dias: int = 30) -> list:
    client = Socrata(
        config["socrata"]["domain"],
        app_token,
        timeout=30,
    )

    all_keywords = []
    for cat_data in config["categories"].values():
        all_keywords.extend(cat_data["keywords"])

    where = _build_where_clause(
        all_keywords,
        departamento=config["departamento_filter"],
        modalidad=config["modalidad_filter"],
        estado=config["estado_filter"],
        dias=dias,
    )
    log.info("Consultando Socrata — departamento: %s | modalidad: %s | keywords: %d",
             config["departamento_filter"], config["modalidad_filter"], len(all_keywords))

    raw_records = _fetch_all_pages(
        client,
        config["socrata"]["dataset_id"],
        where,
        page_size=config["socrata"].get("page_size", 1000),
    )
    log.info("Total registros obtenidos de Socrata: %d", len(raw_records))

    enriched = []
    for record in raw_records:
        norm = _normalize(record)
        if not norm["id_proceso"]:
            continue
        search_text = f"{norm['nombre_proceso']} {norm['objeto']}"
        norm["categoria"] = _classify_category(search_text, config["categories"])
        enriched.append(norm)

    # Filtro por rango de valor según capacidad de la empresa
    try:
        from pathlib import Path as _P
        with open(_P(__file__).parent / "config" / "empresa.json", encoding="utf-8") as f:
            emp = json.load(f)
        val_min = emp.get("valor_minimo_interes_cop", 0)
        val_max = emp.get("valor_maximo_capacidad_cop", None)
        before = len(enriched)
        enriched = _filter_by_value(enriched, val_min, val_max)
        log.info("Filtro de valor [%s — %s COP]: %d → %d procesos",
                 f"{val_min:,.0f}", f"{val_max:,.0f}" if val_max else "∞", before, len(enriched))
    except Exception as e:
        log.warning("No se aplicó filtro de valor: %s", e)

    log.info("Registros normalizados y clasificados: %d", len(enriched))
    return enriched


def fetch_by_id(id_proceso: str, domain: str, dataset_id: str, app_token: str) -> dict | None:
    client = Socrata(domain, app_token, timeout=30)
    id_esc = id_proceso.replace("'", "''")
    records = client.get(
        dataset_id,
        where=f"id_del_proceso='{id_esc}'",
        limit=1,
    )
    if not records:
        return None
    norm = _normalize(records[0])
    norm["_raw"] = records[0]
    return norm
