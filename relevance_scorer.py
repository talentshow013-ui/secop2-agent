import json
import re
import logging
import anthropic
from pathlib import Path

_db_conn = None
_empresa_cache = None

def _get_conn():
    return _db_conn

def set_conn(conn):
    global _db_conn
    _db_conn = conn

log = logging.getLogger(__name__)


def _load_empresa() -> dict:
    global _empresa_cache
    if _empresa_cache is None:
        try:
            with open(Path(__file__).parent / "config" / "empresa.json", encoding="utf-8") as f:
                _empresa_cache = json.load(f)
        except Exception as e:
            log.warning("No se pudo cargar empresa.json: %s", e)
            _empresa_cache = {}
    return _empresa_cache


def _build_system_prompt() -> list:
    e = _load_empresa()
    capacidades = "\n".join(f"- {c}" for c in e.get("capacidades", []))
    entidades = "\n".join(f"- {ent}" for ent in e.get("entidades_objetivo", []))
    no_aplicar = "\n".join(f"- {c}" for c in e.get("criterios_no_aplicar", []))
    experiencia = "\n".join(f"- {x}" for x in e.get("experiencia_relevante", []))
    val_min = e.get("valor_minimo_interes_cop", 3000000)
    val_max = e.get("valor_maximo_capacidad_cop", 80000000)

    texto = f"""Eres un evaluador EXPERTO en contratación pública colombiana (SECOP 2) con 15 años de experiencia.
Conoces a fondo: Ley 80 de 1993, Ley 1150 de 2007, Decreto 1082 de 2015, modalidades de selección, requisitos habilitantes, causales de declaración desierta, y trucos del oficio.

═══════════════════════════════════════════════════
EMPRESA A EVALUAR: {e.get('razon_social', 'VECTOR PRO SERVICES S.A.S.')}
═══════════════════════════════════════════════════
- Tipo: {e.get('tipo_empresa', 'Microempresa')}
- Ubicación: {e.get('municipio', 'Rivera')}, {e.get('departamento', 'Huila')}
- Capacidad operacional máxima por contrato: ${val_max:,.0f} COP
- Valor mínimo de interés: ${val_min:,.0f} COP
- Modalidad objetivo: Mínima Cuantía

CAPACIDADES REALES:
{capacidades}

EXPERIENCIA PREVIA:
{experiencia}

ENTIDADES OBJETIVO (donde tiene mejor afinidad):
{entidades}

NO APLICAR (criterios automáticos de descarte):
{no_aplicar}

═══════════════════════════════════════════════════
CRITERIOS DE SCORING (0-100)
═══════════════════════════════════════════════════

1. ALINEACIÓN DEL OBJETO con capacidades reales (35 pts) — SÉ ESTRICTO
   - 35 pts: el objeto ES exactamente lo que la empresa hace (papelería, dotación escolar, refrigerios para eventos, reforestación, mantenimiento locativo)
   - 20 pts: relacionado pero requiere esfuerzo o subcontratación menor
   - 10 pts: tangencialmente relacionado — requeriría adaptarse mucho
   - 0 pts: claramente fuera del alcance o requiere experiencia especializada que no tienen

   IMPORTANTE: sé conservador. Si tienes duda entre 35 y 20, pon 20. Un score inflado lleva a propuestas que pierden.
   EJEMPLOS:
   - "Suministro papelería institucional" → 35 pts (core business)
   - "Suministro ferretería en general" → 15 pts (parcial, no es su fuerte)
   - "Construcción vía terciaria" → 0 pts (obra civil mayor, no aplica)
   - "Mantenimiento locativo institución educativa" → 30 pts (sí aplica)
   - "Refrigerios para taller comunitario" → 35 pts (core business)

2. VIABILIDAD ECONÓMICA (25 pts) — SÉ REALISTA
   - 25 pts: valor entre ${val_min:,.0f} y ${val_max * 0.7:,.0f} COP (rango cómodo)
   - 15 pts: valor entre ${val_max * 0.7:,.0f} y ${val_max:,.0f} COP (límite superior, riesgo capital)
   - 5 pts: valor menor a ${val_min:,.0f} COP (poco rentable)
   - 0 pts: no se especifica valor o excede ${val_max:,.0f} COP

3. ENTIDAD CONTRATANTE (20 pts)
   - 20 pts: alcaldía, gobernación, colegio o entidad pública del Huila
   - 10 pts: entidad nacional con sede en Huila (ICBF, SENA, hospital)
   - 5 pts: entidad poco conocida

4. UBICACIÓN GEOGRÁFICA (10 pts)
   - 10 pts: Rivera o municipios vecinos (Neiva, Campoalegre, Palermo)
   - 7 pts: cualquier municipio del Huila
   - 0 pts: fuera del Huila

5. ANÁLISIS COMPETITIVO + RIESGO (descuento o bonus, hasta ±10 pts)

   BONUS:
   - "Proveedores invitados" = 1 y nombre de empresa coincide → +5 pts (los invitan directamente)
   - "Respuestas/ofertas recibidas" = 0 y proceso fresco → +3 pts (sin competencia aún)
   - Tipo de contrato matchea capacidades reales: +2 pts

   PENALIZACIONES:
   - "Respuestas/ofertas recibidas" > 10 → -5 pts (mucha competencia)
   - "Visualizaciones" > 100 + respuestas > 5 → -3 pts (proceso muy peleado)
   - "Proveedores invitados" = 1 y NO somos los invitados → -8 pts (proceso amañado para otro)
   - Plazo de ejecución < 7 días → -5 pts (poco tiempo para producir)
   - Plazo de ejecución > 180 días para microempresa → -3 pts (capital de trabajo largo)
   - "Estado resumen" indica que ya cerró la oferta → -10 pts (ya no aplica)
   - Objeto demasiado vago o sin valor definido: -3 pts

═══════════════════════════════════════════════════
GUÍAS DE INTERPRETACIÓN — CALIBRACIÓN ESTRICTA
═══════════════════════════════════════════════════

- Score ≥ 80 → ALTA PRIORIDAD (proceso ideal, presentar sí o sí)
- Score 60-79 → RELEVANTE (vale la pena evaluar)
- Score 40-59 → DUDOSO (posible pero con reservas)
- Score < 40 → DESCARTAR

CALIBRACIÓN: En la práctica, solo el 20-30% de los procesos deberían ser ≥ 60.
Si estás dando 80+ a más de la mitad, estás siendo demasiado generoso — ajusta hacia abajo.

REGLAS ABSOLUTAS:
1. SOLO usa los datos del proceso. NO inventes información.
2. Un score inflado es peor que uno bajo — lleva a perder tiempo en procesos que no aplican.
3. Ante la duda, conservador siempre.
4. Justifica brevemente con la razón principal (qué alineó bien y qué no)."""

    return [{"type": "text", "text": texto, "cache_control": {"type": "ephemeral"}}]


SYSTEM_PROMPT = None  # se construye en runtime para cargar empresa.json fresco


def score_batch(processes: list, client: anthropic.Anthropic) -> list:
    if not processes:
        return []

    try:
        import cost_tracker
        conn = _get_conn()
        if conn:
            puede, gastado = cost_tracker.check_budget(conn)
            if not puede:
                log.warning("Presupuesto diario agotado ($%.2f). Saltando scoring.", gastado)
                return []
    except Exception:
        pass

    proc_lines = []
    for i, p in enumerate(processes, 1):
        val_raw = p.get("valor_proceso", "")
        try:
            val_fmt = f"${float(val_raw):,.0f} COP" if val_raw else "no especificado"
        except Exception:
            val_fmt = str(val_raw) or "no especificado"

        # Inteligencia competitiva
        respuestas = p.get('respuestas_ofertas', '0') or '0'
        visualizaciones = p.get('visualizaciones', '0') or '0'
        invitados = p.get('proveedores_invitados', '0') or '0'
        manifestaron = p.get('proveedores_manifestaron', '0') or '0'
        duracion = p.get('duracion', '')
        unidad = p.get('unidad_duracion', '')
        plazo = f"{duracion} {unidad}".strip() if duracion else 'no especificado'

        proc_lines.append(f"""
PROCESO {i}:
- ID: {p.get('id_proceso', 'N/D')}
- Nombre: {p.get('nombre_proceso', 'N/D')}
- Objeto: {(p.get('objeto') or p.get('nombre_proceso') or 'N/D')[:300]}
- Entidad: {p.get('entidad', 'N/D')} (orden: {p.get('orden_entidad', 'N/D')})
- Tipo contrato: {p.get('tipo_contrato', 'N/D')} | Subtipo: {p.get('subtipo_contrato', 'N/D')}
- Valor estimado: {val_fmt}
- Plazo ejecución: {plazo}
- Modalidad: {p.get('modalidad', 'N/D')}
- Ciudad: {p.get('ciudad', 'N/D')}, {p.get('departamento', 'N/D')}
- Fecha publicación: {p.get('fecha_publicacion', 'N/D')[:10]}
- Fecha cierre estimada: {(p.get('fecha_cierre') or 'no especificada')[:10]}
- Fase actual: {p.get('fase', 'N/D')} | Estado: {p.get('estado_resumen', p.get('estado', 'N/D'))}
- INTELIGENCIA COMPETITIVA:
  · Respuestas/ofertas recibidas: {respuestas}
  · Proveedores que manifestaron interés: {manifestaron}
  · Proveedores invitados directamente: {invitados}
  · Visualizaciones del proceso: {visualizaciones}""")

    prompt = f"""Evalúa estos {len(processes)} procesos de contratación pública aplicando los criterios definidos en tu rol.

{''.join(proc_lines)}

Para cada proceso, evalúa los 5 criterios (alineación, viabilidad económica, entidad, ubicación, riesgo) y calcula el score final.

Responde SOLO con JSON válido, sin texto adicional:
{{
  "evaluaciones": [
    {{
      "indice": 1,
      "id_proceso": "...",
      "score": 75,
      "justificacion": "Por qué le diste ese score, mencionando lo principal: alineación, valor, entidad, y cualquier señal de riesgo detectada. Máximo 2 oraciones, claro y directo.",
      "categoria": "suministro|eventos|social|ambiental|mantenimiento|otro"
    }}
  ]
}}"""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            system=_build_system_prompt(),
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        try:
            import cost_tracker
            cost_tracker.register_usage(
                _get_conn(), "claude-haiku-4-5-20251001", "scoring",
                response.usage.input_tokens, response.usage.output_tokens
            )
        except Exception:
            pass
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not json_match:
            log.error("Claude no retornó JSON válido: %s", raw[:200])
            return []
        data = json.loads(json_match.group())
        return data.get("evaluaciones", [])
    except Exception as e:
        log.error("Error en scoring batch: %s", e)
        return []


def score_processes(processes: list, client: anthropic.Anthropic, batch_size: int = 8) -> list:
    scored = []
    for i in range(0, len(processes), batch_size):
        batch = processes[i:i + batch_size]
        results = score_batch(batch, client)
        score_map = {r.get("id_proceso", ""): r for r in results if r.get("id_proceso")}
        for proc in batch:
            pid = proc.get("id_proceso", "")
            if pid in score_map:
                proc["_score"] = score_map[pid].get("score", 0)
                proc["_justificacion"] = score_map[pid].get("justificacion", "")
                proc["_categoria_claude"] = score_map[pid].get("categoria", "otro")
            else:
                proc["_score"] = 0
                proc["_justificacion"] = "No evaluado"
                proc["_categoria_claude"] = "otro"
            scored.append(proc)
    return scored
