import os
import re
import logging
from datetime import date
import anthropic
from docx import Document
from docx.shared import Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH

log = logging.getLogger(__name__)

DRAFT_NOTE = "BORRADOR DE REFERENCIA — GENERADO CON DATOS REALES DE SECOP II — VERIFICAR ANTES DE PRESENTAR"

EMPRESA = {
    "nombre":    "VECTOR PRO SERVICES S.A.S.",
    "municipio": "Rivera, Huila",
    "tipo":      "Microempresa",
    "modalidad": "Mínima Cuantía",
}

# Instrucciones muy estrictas por sección — mínima libertad creativa
SECTIONS = [
    {
        "key":    "caratula",
        "titulo": "1. CARÁTULA DEL PROCESO",
        "prompt": """Con los datos del proceso que te doy, redacta SOLO la carátula en formato de tabla texto con estos campos exactos:
- Número/ID del proceso: [usar id_proceso]
- Entidad contratante: [usar entidad]
- Objeto del contrato: [usar objeto]
- Modalidad de selección: [usar modalidad]
- Valor estimado: [usar valor_proceso] COP
- Departamento: [usar departamento]
- Municipio: [usar ciudad]
- Fecha de publicación: [usar fecha_publicacion]
- Estado: [usar estado]
- Empresa oferente: VECTOR PRO SERVICES S.A.S. — Rivera, Huila

Si algún campo no está en los datos, escribe literalmente [DATO NO DISPONIBLE EN SECOP II].
NO agregues ningún campo que no esté en la lista anterior. NO inventes información.""",
    },
    {
        "key":    "estudios_previos",
        "titulo": "2. ESTUDIOS PREVIOS Y DE CONVENIENCIA",
        "prompt": """Redacta los estudios previos según Art. 30 Ley 80/1993 y Art. 3 Dec. 1082/2015.

REGLA: Solo usa los datos del proceso. Para cada sección que no tenga datos suficientes escribe la sección con lo que hay y marca [COMPLETAR CON INFORMACIÓN DE LA ENTIDAD].

Secciones obligatorias (redáctalas todas aunque sea con marcadores):
1. DESCRIPCIÓN DE LA NECESIDAD
   Basarte en el objeto del proceso: {objeto}. Explicar por qué la entidad requiere este bien o servicio.

2. OBJETO A CONTRATAR
   Transcribir y ampliar el objeto: {objeto}

3. FUNDAMENTO JURÍDICO DE LA MODALIDAD
   Justificar por qué aplica Mínima Cuantía según Dec. 1082/2015 Art. 2.2.1.2.1.2.4.

4. VALOR ESTIMADO
   El valor del proceso es: {valor_proceso} COP.
   Indicar que fue determinado mediante estudio de mercado [COMPLETAR CON COTIZACIONES].

5. PLAZO DE EJECUCIÓN
   [COMPLETAR CON PLAZO DEFINIDO POR LA ENTIDAD]

NO inventes valores específicos de cotizaciones, fechas exactas ni datos de la entidad que no estén en los datos proporcionados.""",
    },
    {
        "key":    "analisis_sector",
        "titulo": "3. ANÁLISIS DEL SECTOR",
        "prompt": """Elabora el análisis del sector según Dec. 1082/2015 Art. 2.2.1.1.1.6.1.

Basa TODO en el tipo de bien o servicio que se describe en el objeto: {objeto}

Secciones:
1. DESCRIPCIÓN DEL MERCADO RELEVANTE
   Describe el mercado de este tipo de bien/servicio en Colombia, en términos generales y reales.

2. ANÁLISIS DE LA OFERTA
   Describe el perfil general de proveedores que pueden ejecutar este contrato en Colombia.
   NO nombres empresas específicas. Solo describe el tipo de proveedor.

3. PRECIOS DE REFERENCIA
   Indica rangos de precios aproximados de mercado colombiano para este tipo de bien/servicio.
   Sé conservador — no inventes cifras precisas. Usa rangos amplios y marca como "referencial".

4. NORMATIVA APLICABLE
   Lista la normativa colombiana aplicable al sector de este bien o servicio.

Si no tienes información suficiente sobre algún punto, escríbelo y marca [AMPLIAR CON ESTUDIO DE MERCADO ESPECÍFICO].""",
    },
    {
        "key":    "analisis_riesgo",
        "titulo": "4. ANÁLISIS DE RIESGO",
        "prompt": """Elabora la matriz de riesgo del proceso en formato de tabla de texto con columnas:
TIPO | DESCRIPCIÓN | PROBABILIDAD (Alta/Media/Baja) | IMPACTO (Alto/Medio/Bajo) | MEDIDA DE MITIGACIÓN | RESPONSABLE

Incluye exactamente estos 6 riesgos ajustados al objeto del proceso ({objeto}):
1. Incumplimiento del proveedor en calidad o plazo
2. Insuficiencia presupuestal o bloqueo del CDP
3. Fuerza mayor o caso fortuito
4. Inconformidad en la calidad del bien/servicio entregado
5. Riesgo jurídico (impugnaciones, nulidades)
6. Riesgo específico del sector (ajústalo al tipo de bien/servicio)

Sé realista con las probabilidades e impactos. No exageres.""",
    },
    {
        "key":    "ficha_tecnica",
        "titulo": "5. FICHA TÉCNICA DEL BIEN O SERVICIO",
        "prompt": """Genera la ficha técnica basándote ÚNICAMENTE en el objeto del proceso: {objeto}

Determina si es SUMINISTRO, SERVICIO o MANTENIMIENTO según el objeto y aplica el formato correcto:

Si es SUMINISTRO:
Tabla: N° | Ítem | Descripción | Unidad de medida | Cantidad estimada | Especificación mínima
Para cantidades no especificadas en los datos, escribe [SEGÚN NECESIDAD DE LA ENTIDAD]

Si es SERVICIO:
- Alcance del servicio
- Actividades a ejecutar
- Entregables esperados
- Perfil del ejecutor requerido
- Lugar de ejecución: {ciudad}, {departamento}

Si es MANTENIMIENTO:
- Actividades específicas
- Materiales o insumos requeridos
- Estándares de calidad aplicables

Marca con [COMPLETAR] todo lo que no puedas deducir del objeto del proceso.""",
    },
    {
        "key":    "cdp",
        "titulo": "6. CERTIFICADO DE DISPONIBILIDAD PRESUPUESTAL (CDP)",
        "prompt": """Genera el formato de CDP con la estructura oficial colombiana.

IMPORTANTE: Este es un formato en blanco con los campos de los datos del proceso.
NO inventes número de CDP, rubro presupuestal específico, ni código SIIF.

Formato:
REPÚBLICA DE COLOMBIA
[NOMBRE DE LA ENTIDAD: usar {entidad}]

CERTIFICADO DE DISPONIBILIDAD PRESUPUESTAL
No. CDP: [NÚMERO ASIGNADO POR LA ENTIDAD]

El suscrito Jefe de Presupuesto o quien hace sus veces, CERTIFICA que existe disponibilidad
presupuestal para atender el compromiso por valor de {valor_proceso} COP correspondiente a:

Objeto: {objeto}
Rubro presupuestal: [COMPLETAR SEGÚN PLAN PRESUPUESTAL DE LA ENTIDAD]
Vigencia fiscal: [AÑO EN CURSO]
Código SIIF: [COMPLETAR]

Firma: [JEFE DE PRESUPUESTO O QUIEN HACE SUS VECES]
Cargo: [COMPLETAR]
Fecha: [COMPLETAR]

Nota: Todos los campos en [COMPLETAR] deben ser diligenciados por la entidad contratante.""",
    },
    {
        "key":    "pliego",
        "titulo": "7. PLIEGO DE CONDICIONES",
        "prompt": """Redacta el pliego de condiciones para proceso de Mínima Cuantía según Dec. 1082/2015.

Usa los datos del proceso para llenar cada sección. Lo que no tengas datos, marca [COMPLETAR].

SECCIONES OBLIGATORIAS:

1. OBJETO
   {objeto} — Entidad: {entidad}

2. PRESUPUESTO OFICIAL
   Valor: {valor_proceso} COP (incluido IVA si aplica)

3. PLAZO DE EJECUCIÓN
   [COMPLETAR — SEGÚN CRONOGRAMA DE LA ENTIDAD]

4. CAPACIDAD PARA CONTRATAR
   Personas naturales o jurídicas, nacionales o extranjeras, con capacidad legal para contratar.
   No inhabilidades ni incompatibilidades según Ley 80/1993.

5. REQUISITOS HABILITANTES
   Jurídicos: RUT vigente, Cámara de Comercio con objeto social relacionado, certificado de existencia.
   Financieros: Indicadores financieros básicos [COMPLETAR UMBRALES SEGÚN VALOR DEL PROCESO].
   Técnicos: Experiencia en contratos similares [COMPLETAR EXPERIENCIA MÍNIMA].

6. CRITERIOS DE SELECCIÓN
   Para Mínima Cuantía: Menor precio con cumplimiento de requisitos habilitantes.

7. CRONOGRAMA
   Publicación del proceso: {fecha_publicacion}
   Cierre y apertura de ofertas: [COMPLETAR]
   Adjudicación: [COMPLETAR]
   Suscripción del contrato: [COMPLETAR]

8. FORMA DE PAGO
   [COMPLETAR — SEGÚN DISPONIBILIDAD PRESUPUESTAL DE LA ENTIDAD]

9. GARANTÍAS
   Cumplimiento del contrato: [COMPLETAR PORCENTAJE Y VIGENCIA]""",
    },
    {
        "key":    "propuesta",
        "titulo": "8. PROPUESTA ECONÓMICA — VECTOR PRO SERVICES S.A.S.",
        "prompt": """Genera la propuesta económica de VECTOR PRO SERVICES S.A.S. como proponente.

IMPORTANTE:
- El valor total de la propuesta NO debe superar {valor_proceso} COP (presupuesto oficial)
- Los precios unitarios deben ser coherentes con el mercado colombiano para: {objeto}
- Marca los precios como "REFERENCIALES DE MERCADO — Ajustar con cotizaciones propias"

ESTRUCTURA:

1. CARTA DE PRESENTACIÓN
   Ciudad y fecha: Rivera, Huila, [FECHA DE PRESENTACIÓN]
   Dirigida a: [NOMBRE DEL REPRESENTANTE LEGAL DE {entidad}]
   Cargo: [COMPLETAR]

   Texto formal ofreciendo los bienes/servicios del proceso {id_proceso}.
   Mencionar experiencia de VECTOR PRO SERVICES en el sector.
   Datos del proponente:
   - Empresa: VECTOR PRO SERVICES S.A.S.
   - NIT: [COMPLETAR]
   - Representante Legal: [COMPLETAR]
   - Dirección: Rivera, Huila
   - Teléfono: [COMPLETAR]
   - Email: [COMPLETAR]

2. OFERTA ECONÓMICA
   Tabla de ítems coherente con el objeto del proceso.
   Valor total: Igual o inferior a {valor_proceso} COP.
   Los precios deben ser razonables para el tipo de bien/servicio.
   Nota al pie: "Precios referenciales. Actualizar con cotizaciones de proveedores antes de presentar."

3. EXPERIENCIA RELACIONADA
   [COMPLETAR CON CONTRATOS EJECUTADOS POR VECTOR PRO SERVICES EN EL SECTOR]

4. DOCUMENTOS ADJUNTOS (lista de chequeo)
   [ ] RUT actualizado
   [ ] Cámara de Comercio vigente
   [ ] Cédula representante legal
   [ ] Certificados de experiencia
   [ ] Estados financieros [si aplica por cuantía]
   [ ] Garantía de seriedad de la oferta [si la solicita el pliego]""",
    },
]


def _build_context(proc: dict, docs_text: str = "") -> str:
    base = (
        f"DATOS REALES DEL PROCESO (FUENTE: SECOP II / API SOCRATA):\n"
        f"id_proceso     = {proc.get('id_proceso', 'NO DISPONIBLE')}\n"
        f"objeto         = {proc.get('objeto', proc.get('nombre_proceso', 'NO DISPONIBLE'))}\n"
        f"entidad        = {proc.get('entidad', 'NO DISPONIBLE')}\n"
        f"modalidad      = {proc.get('modalidad', 'Mínima Cuantía')}\n"
        f"estado         = {proc.get('estado', 'NO DISPONIBLE')}\n"
        f"valor_proceso  = {proc.get('valor_proceso', 'NO DISPONIBLE')}\n"
        f"fecha_pub      = {proc.get('fecha_publicacion', 'NO DISPONIBLE')}\n"
        f"departamento   = {proc.get('departamento', 'Huila')}\n"
        f"ciudad         = {proc.get('ciudad', 'NO DISPONIBLE')}\n"
        f"fase           = {proc.get('fase', 'NO DISPONIBLE')}\n"
        f"url_secop      = {proc.get('url_secop', '')}\n"
    )
    if docs_text:
        base += (
            f"\n{'─'*50}\n"
            f"DOCUMENTOS OFICIALES DESCARGADOS DE SECOP II:\n"
            f"(Usa esta información como fuente primaria — es el texto real de los documentos del proceso)\n\n"
            f"{docs_text}\n"
        )
    return base


def _fill_prompt(template: str, proc: dict) -> str:
    replacements = {
        "{objeto}":           proc.get("objeto", proc.get("nombre_proceso", "[OBJETO NO DISPONIBLE]")),
        "{entidad}":          proc.get("entidad", "[ENTIDAD NO DISPONIBLE]"),
        "{valor_proceso}":    proc.get("valor_proceso", "[VALOR NO DISPONIBLE]"),
        "{fecha_publicacion}":proc.get("fecha_publicacion", "[FECHA NO DISPONIBLE]"),
        "{departamento}":     proc.get("departamento", "Huila"),
        "{ciudad}":           proc.get("ciudad", "[MUNICIPIO NO DISPONIBLE]"),
        "{id_proceso}":       proc.get("id_proceso", "[ID NO DISPONIBLE]"),
    }
    for placeholder, value in replacements.items():
        template = template.replace(placeholder, str(value))
    return template


def _call_claude(context: str, instruction: str, client: anthropic.Anthropic) -> str:
    try:
        import cost_tracker, db_manager
        from pathlib import Path
        db_path = Path(__file__).parent / "secop.db"
        c = db_manager.get_connection(str(db_path))
        puede, gastado = cost_tracker.check_budget(c)
        c.close()
        if not puede:
            return f"[SECCIÓN NO GENERADA — Presupuesto diario Claude agotado (${gastado:.2f}). Mañana se reanuda.]"
    except Exception:
        pass

    prompt = (
        f"{context}\n"
        f"{'─'*50}\n"
        f"INSTRUCCIÓN:\n{instruction}\n\n"
        f"REGLAS ABSOLUTAS:\n"
        f"1. Usa ÚNICAMENTE los datos de arriba. No inventes ningún dato.\n"
        f"2. Si un dato no está disponible, escribe [COMPLETAR] — nunca inventes.\n"
        f"3. Redacta en español jurídico colombiano formal.\n"
        f"4. No pongas introducción ni cierre — ve directo al contenido de la sección."
    )
    try:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        try:
            import cost_tracker, db_manager
            from pathlib import Path
            db_path = Path(__file__).parent / "secop.db"
            c = db_manager.get_connection(str(db_path))
            cost_tracker.register_usage(
                c, "claude-sonnet-4-6", "doc_generation",
                resp.usage.input_tokens, resp.usage.output_tokens
            )
            c.close()
        except Exception:
            pass
        return resp.content[0].text.strip()
    except Exception as e:
        log.error("Error generando sección: %s", e)
        return f"[ERROR AL GENERAR ESTA SECCIÓN: {e}]"


def _add_heading(doc: Document, text: str, level: int = 1):
    p = doc.add_heading(text, level=level)
    for run in p.runs:
        run.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)


def _add_watermark(doc: Document):
    p = doc.add_paragraph(DRAFT_NOTE)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in p.runs:
        run.font.bold  = True
        run.font.size  = Pt(8)
        run.font.color.rgb = RGBColor(0xC0, 0x00, 0x00)


def _add_content(doc: Document, text: str):
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# "):
            _add_heading(doc, stripped[2:], 1)
        elif stripped.startswith("## "):
            _add_heading(doc, stripped[3:], 2)
        elif stripped.startswith("### "):
            _add_heading(doc, stripped[4:], 3)
        elif stripped.startswith(("- ", "* ", "• ")):
            doc.add_paragraph(stripped[2:], style="List Bullet")
        elif re.match(r'^\d+\.', stripped):
            doc.add_paragraph(stripped, style="List Number")
        else:
            p = doc.add_paragraph()
            if stripped.startswith("**") and stripped.endswith("**"):
                run = p.add_run(stripped.strip("*"))
                run.bold = True
            else:
                p.add_run(stripped)


def generate_secop_document(proc: dict, client: anthropic.Anthropic, output_dir: str, texto_previo: str = "") -> str:
    import secop_playwright

    id_proceso = proc.get("id_proceso", "PROCESO")
    url_proceso = proc.get("url_secop", "")

    # Si ya se analizó el proceso antes, usa ese texto directamente
    if texto_previo:
        docs_text = texto_previo
        log.info("Usando análisis previo: %d chars", len(docs_text))
    elif url_proceso and url_proceso != "#":
        # Si no, descarga ahora
        log.info("Descargando documentos del proceso %s", id_proceso)
        try:
            scraped = secop_playwright.scrape_proceso_docs(url_proceso, headless=True)
            docs_text = scraped.get("texto_completo", "")
            if docs_text:
                log.info("Documentos obtenidos: %d chars", len(docs_text))
            elif scraped.get("error"):
                log.warning("No se pudieron obtener documentos: %s", scraped["error"])
        except Exception as e:
            log.warning("Error en Playwright: %s — generando con datos de Socrata", e)
            docs_text = ""
    else:
        docs_text = ""

    context = _build_context(proc, docs_text)

    doc = Document()
    for section in doc.sections:
        section.left_margin   = Cm(3)
        section.right_margin  = Cm(2.5)
        section.top_margin    = Cm(2.5)
        section.bottom_margin = Cm(2.5)

    # Portada
    doc.add_paragraph()
    t = doc.add_paragraph("VECTOR PRO SERVICES S.A.S.")
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    t.runs[0].bold = True
    t.runs[0].font.size = Pt(16)
    t.runs[0].font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)

    sub = doc.add_paragraph(f"Documentos de Postulación — Proceso SECOP II")
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub.runs[0].font.size = Pt(12)

    id_p = doc.add_paragraph(f"ID: {id_proceso}")
    id_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    fecha_p = doc.add_paragraph(f"Generado: {date.today().strftime('%d de %B de %Y')}")
    fecha_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    _add_watermark(doc)
    doc.add_page_break()

    # Índice simple
    _add_heading(doc, "CONTENIDO DEL DOCUMENTO", 1)
    for s in SECTIONS:
        doc.add_paragraph(s["titulo"], style="List Number")
    doc.add_page_break()

    # Secciones
    for s in SECTIONS:
        log.info("Generando: %s", s["titulo"])
        _add_heading(doc, s["titulo"], 1)
        _add_watermark(doc)
        instruction = _fill_prompt(s["prompt"], proc)
        content     = _call_claude(context, instruction, client)
        _add_content(doc, content)
        doc.add_page_break()

    # Pie de página informativo
    p = doc.add_paragraph(
        f"Documento generado el {date.today()} por el Asistente SECOP 2 de VECTOR PRO SERVICES S.A.S.\n"
        f"Fuente de datos: SECOP II via API Socrata (datos.gov.co) — ID proceso: {id_proceso}\n"
        f"Este borrador es una referencia de trabajo. Todos los campos [COMPLETAR] deben ser "
        f"diligenciados con información real de la empresa y la entidad antes de presentar."
    )
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in p.runs:
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor(0x80, 0x80, 0x80)

    safe_id    = re.sub(r'[^\w\-]', '_', id_proceso)
    filename   = f"SECOP2_{safe_id}_{date.today().strftime('%Y%m%d')}.docx"
    output_path = os.path.join(output_dir, filename)
    doc.save(output_path)
    log.info("Documento guardado: %s", output_path)
    return output_path
