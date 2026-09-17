# SECOP2 Agent — guía para Claude Code

Agente de contratación pública para VECTOR PRO SERVICES S.A.S. (Rivera, Huila). Bot de Telegram
conversacional con alertas por Telegram + scripts de investigación sobre datos abiertos de SECOP II.
Lee `README.md` para instalación y `MEMORY.md` para el historial detallado del proyecto.

## Cómo correr
```bash
python -m venv .venv && .venv/Scripts/activate      # Windows; en Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                                  # y llenar credenciales
python main.py                                        # bot + scheduler 08:00 | 14:00 | 20:00
```
`start.bat` hace todo lo anterior en Windows. No hay panel web: la interfaz es el bot de Telegram (retirado del repo el 2026-09-17). Playwright es opcional (ver limitaciones).

### Modo solo investigación (sin Telegram ni API de Anthropic)
Si este repo se usa únicamente para consultar SECOP desde Claude Code, **no hace falta ninguna
credencial**: los scripts de `research/` solo usan la API pública de datos.gov.co.
```bash
python -m venv .venv && .venv/Scripts/activate
pip install -r requirements-research.txt          # solo sodapy + python-dotenv
python research/buscar_procesos.py salida.json    # funciona sin .env (verificado en clon limpio 2026-09-16)
```
Opcional: crear `.env` con solo `SOCRATA_APP_TOKEN=...` para evitar el throttling. No tocar
`main.py` ni `doc_generator.py` en este modo — esos sí exigen las demás credenciales.

## De dónde salen los datos: API Socrata de datos.gov.co
Todo viene de la **API SODA (Socrata Open Data API)** de `www.datos.gov.co`, vía `sodapy`.
No hay API oficial de SECOP: los datasets abiertos son la única vía programática.
Token gratuito en datos.gov.co → Developer Settings → `SOCRATA_APP_TOKEN` en `.env` (sin token
funciona pero con throttling fuerte).

| Dataset | ID | Qué es | Clave para cruzar |
|---|---|---|---|
| SECOP II — Procesos de Contratación | `p6dx-8zbt` | 1 fila por proceso (licitación). Lo usa el bot. | `id_del_proceso`, `nit_entidad`, `referencia_del_proceso` |
| SECOP II — Contratos Electrónicos | `jbjy-vk9h` | 1 fila por contrato firmado. Trae rep. legal, supervisor, datos bancarios. | `documento_proveedor` (NIT) |
| Proponentes por Proceso SECOP II | `hgi6-6wh3` | 1 fila por proveedor que ofertó en un proceso — **quién compite** | `nit_entidad` + `nombre_procedimiento` |
| SECOP I (portal viejo) | `x6v4-i8gf` | Contratos 2011–2020 aprox. | `identificacion_del_contratista` |

Campos útiles de `p6dx-8zbt`: `entidad`, `nombre_del_procedimiento`, `descripci_n_del_procedimiento`,
`modalidad_de_contratacion`, `estado_del_procedimiento` (Publicado / Abierto / Evaluación /
Seleccionado / Cancelado), `fase`, `precio_base`, `fecha_de_publicacion_del`, `fecha_de_recepcion_de`
(cierre de ofertas), `duracion` + `unidad_de_duracion`, `nombre_del_proveedor` y
`nit_del_proveedor_adjudicado` (ganador), `valor_total_adjudicacion`, `urlproceso`.

### Trampas conocidas (aprendidas a golpes)
- **Agrupar siempre por NIT, nunca por nombre** — el nombre de una misma empresa varía entre filas.
  Excluir NIT `No Definido` / `000000000` (mezcla cientos de proveedores).
- `id_del_proceso` de `p6dx-8zbt` **no coincide** con `id_procedimiento` de `hgi6-6wh3` para el
  mismo proceso. Cruzar por `nit_entidad` + nombre del procedimiento.
- `referencia_del_proceso` (ej. `LP-001-2026`) se repite en cientos de entidades — nunca cruzar solo
  por referencia.
- El estado `Publicado/Abierto` no siempre se actualiza: filtrar además por `fecha_de_recepcion_de >= hoy`
  para saber qué está realmente abierto.
- Un mismo proceso aparece varias veces en `p6dx-8zbt` (una fila por fase: borrador, observaciones,
  ofertas, seleccionado). Para cronologías, agrupar por entidad + nombre.
- Procesos en fase "Presentación de observaciones" aún no tienen proponentes en ningún dataset.
- Ningún dataset tiene correo electrónico del proveedor ni de la entidad.
- Agregaciones (`min/max/count`) sobre `hgi6-6wh3` completo hacen timeout; filtrar por NIT primero.
- Los contratos de "socio estratégico / sociedad de economía mixta" para alumbrado son en la práctica
  concesiones a 20 años, pero no contienen la palabra "concesión" — buscar ambas cosas.

## Limitación dura: los PDFs de los procesos NO se pueden descargar por script
SECOP II (`community.secop.gov.co`) redirige toda URL de proceso a un reCAPTCHA; SECOP I
(`contratos.gov.co`) muestra la página pero cada PDF pasa por reCAPTCHA v3. Verificado 2026-09-15.
**No intentar sortear el captcha.** Vía correcta: un humano descarga el PDF en el navegador y lo
deja en `output/docs/` (Claude Code lo lee directo) o se lo reenvía al bot por Telegram.
`secop_playwright.py` existe pero solo devuelve la pantalla del captcha.

## Preferencias de trabajo del operador
- Perfil técnico, consciente del gasto de tokens. Para reportes grandes: script que escriba el `.md`
  **directo a disco** y leer solo una muestra; `.md → .docx` con `pandoc input.md -o output.docx --toc`.
- "Todo es todo": cuando pide el dataset completo, no recortar.
- Respuestas cortas y al grano. Español.
- El usuario final del bot (ingeniero ambiental) es otra persona, no técnica — la interfaz del bot es
  100 % lenguaje natural, sin comandos.

## Estructura
```
main.py               bot Telegram + scheduler          secop_scraper.py    consultas Socrata p6dx-8zbt
relevance_scorer.py   Claude Haiku, scoring en batch     doc_generator.py    Word 8 secciones (Claude Sonnet)
db_manager.py         SQLite (procesos, run_log)         report_generator.py Excel por categoría
config/keywords.json  filtros (Huila, Mínima Cuantía, 5 categorías)
config/empresa.json   perfil de la empresa para los documentos
research/             scripts de inteligencia de mercado (ver research/README.md)
output/               reportes generados (ignorado en git)
```

## Filtros actuales del bot y su punto ciego
Departamento Huila, modalidad "Mínima Cuantía" únicamente, 5 categorías de keywords. Entidades que
contratan por Contratación directa / régimen especial (ej. Corporación Nasa Kiwe) nunca son detectadas.

## Indicadores de riesgo (banderas rojas) que se pueden calcular con estos datos
Oferente único; ventana de ofertas < 15 días en contratos grandes o en festivos; mismo consultor del
Estudio Técnico de Referencia → mismo ganador; adjudicación al 97–100 % del presupuesto; procesos
duplicados la misma semana. Son indicadores, **no prueba de corrupción** — la prueba está en pliegos y
actas (PDFs) y en vínculos societarios (RUES), no en SECOP.
