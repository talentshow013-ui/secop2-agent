# Memoria del Proyecto — Agente SECOP 2
## Última actualización: 2026-07-14

---

## QUÉ ES ESTE PROYECTO
Agente de contratación pública para VECTOR PRO SERVICES S.A.S. (Rivera, Huila).
Consulta SECOP 2 automáticamente 3 veces al día via API Socrata y genera documentos Word de postulación.
El usuario final es un ingeniero ambiental — la interfaz es 100% conversacional en Telegram.

---

## CLIENTE
- **Empresa**: VECTOR PRO SERVICES S.A.S. — microempresa, Rivera, Huila
- **Usuario/dueño**: Yeisson Silva Murcia — administrador público, maestría en economía, gerencia de proyectos
- **Usuario final del bot**: Un ingeniero ambiental (no técnico) — NO sabe de comandos
- **Preferencia Yeisson**: Respuestas cortas, al grano, sin gastar tokens

---

## ESTADO ACTUAL DEL PROYECTO — COMPLETADO Y FUNCIONAL

### Archivos creados en c:\Users\redom\Desktop\MIS AGENTES\SECOP2\
```
├── main.py              ← Bot Telegram conversacional + scheduler 08:00|14:00|20:00
├── secop_scraper.py     ← Socrata API, paginación, retry exponencial
├── relevance_scorer.py  ← Claude Haiku scoring en batches de 8 + prompt caching
├── db_manager.py        ← SQLite: tablas procesos + run_log
├── doc_generator.py     ← Word 8 secciones anti-alucinación (datos reales Socrata)
├── report_generator.py  ← Excel por categoría (verde ≥80, amarillo ≥60)
├── config/keywords.json ← 5 categorías + filtros Huila
├── .env                 ← Credenciales reales YA CONFIGURADAS
├── .env.example         ← Template limpio
└── requirements.txt
```

### Credenciales en .env — YA CONFIGURADAS
- TELEGRAM_TOKEN ✓
- TELEGRAM_CHAT_ID ✓
- ANTHROPIC_API_KEY ✓
- SOCRATA_APP_TOKEN ✓

### Para correr
```bash
cd "c:/Users/redom/Desktop/MIS AGENTES/SECOP2"
pip install -r requirements.txt
python main.py
```

---

## STACK TÉCNICO
- Python 3 + Telegram Bot (pyTelegramBotAPI)
- Socrata API → datos.gov.co → dataset `p6dx-8zbt` (SECOP II procesos)
- Claude Haiku 4.5 → scoring de relevancia (batches de 8, prompt caching)
- Claude Sonnet 4.6 → generación de documentos Word (8 secciones)
- `schedule` library → 08:00 | 14:00 | 20:00
- SQLite → deduplicación e historial
- openpyxl → reporte Excel por categoría

---

## CÓMO FUNCIONA EL BOT
- **Conversacional**: Claude Haiku interpreta intención en lenguaje natural
- El ingeniero escribe: "busca procesos", "genera documentos del proceso X", "muéstrame los últimos"
- NO usa slash commands — todo lenguaje natural
- Al encontrar procesos score ≥ 60: alerta Telegram + genera Word del mejor automáticamente
- El Word tiene 8 secciones basadas ÚNICAMENTE en datos reales de Socrata
- Campos sin datos = [COMPLETAR] — nunca alucina

---

## FILTROS DE BÚSQUEDA
- Departamento: **Todo el Huila** (no solo Rivera)
- Modalidad: Mínima Cuantía
- Estado: Publicado
- 5 categorías: suministro | eventos | social | ambiental | mantenimiento

---

## DOCUMENTO WORD — 8 SECCIONES
1. Carátula del proceso
2. Estudios Previos y de Conveniencia (Art. 30 Ley 80/1993)
3. Análisis del Sector (Dec. 1082/2015)
4. Análisis de Riesgo (matriz)
5. Ficha Técnica del bien/servicio
6. CDP — placeholder con [COMPLETAR]
7. Pliego de Condiciones
8. Propuesta Económica (desde Vector Pro Services)

---

## DASHBOARD WEB — ✅ COMPLETADO (confirmado 2026-07-14)
El dashboard ya está construido y funcional: `dashboard_api.py` (FastAPI con auth básica
`DASHBOARD_USER`/`DASHBOARD_PASS`) + `dashboard.html` (Tailwind). Se corre con `start.bat`
o manualmente (`python dashboard_api.py`, abrir `http://localhost:8000`). Ver README.md
para detalle de instalación y endpoints reales. La sección anterior de este archivo lo
describía como "próximo paso" — eso ya no es cierto, quedó desactualizado desde ~30-abr.

---

## SESIÓN 2026-07-14 — Investigación de inteligencia competitiva vía Claude Code

Aparte del bot/dashboard, se usó Claude Code directamente (fuera de Telegram) para
consultas puntuales de investigación sobre datos de SECOP2. Quien opera Claude Code en
estas sesiones es un perfil más técnico que el ingeniero ambiental que usa el bot por
Telegram — cómodo con detalle técnico, consciente del gasto de tokens, y pide "todo el
dato crudo" cuando lo pide explícitamente (no resúmenes).

### Qué se hizo
1. **Perfil completo de la Corporación Nasa Kiwe** (entidad nacional que atiende
   comunidades indígenas Nasa en Cauca y Huila tras el desastre de 1994) — procesos como
   compradora, procesos donde aparecen como proveedor, contratos como compradora (1,513)
   y contratos donde son contratistas (26). Entregado en
   `output/NASA_KIWE_informe_completo.md` + `.docx` (3,019 registros totales).
   - Hallazgo clave: bajo "Nasa Kiwe" hay VARIAS organizaciones legalmente distintas
     (la Corporación nacional vs. resguardos/cabildos indígenas como "Resguardo Indígena
     Nasa Kiwe Tekh Ksxaw" en Cauca o "Cabildo Indígena Nasa Kiwe Nxusxa" en Putumayo).
     No confundirlas en futuros análisis.
   - Oportunidad detectada: la Corporación opera también en Huila (ej. contrato de placa
     huella en La Plata, Huila) pero contrata por "Contratación directa"/"régimen
     especial", NO Mínima Cuantía — el filtro actual del bot (`modalidad_filter` en
     `config/keywords.json`) nunca la detectaría. Si se quiere monitorear como fuente de
     oportunidades, hay que agregarla como búsqueda por entidad aparte del filtro actual.

2. **Ranking nacional de empresas de obra civil** (dataset Contratos Electrónicos,
   `tipo_de_contrato='Obra'`, últimos 12 meses, agrupado por NIT, ordenado por cantidad
   de contratos). Entregado en `output/Ranking_Obras_Civiles_Colombia_Top50.md` + `.docx`.
   - Cuidado: casi la mitad del top 50 son "Empresas de Desarrollo Urbano" municipales,
     alcaldías o gremios (no competencia real), no solo constructoras privadas — hay que
     revisar el campo nombre antes de tratar cualquier fila como "empresa privada".
   - El NIT "No Definido"/"000000000" es un artefacto de datos que mezcla cientos de
     proveedores sin NIT diligenciado — siempre excluirlo al agrupar, no es una empresa.

3. **Confirmado sobre los datasets Socrata de SECOP2** (`p6dx-8zbt` Procesos,
   `jbjy-vk9h` Contratos Electrónicos — datos.gov.co):
   - NO existe campo de correo electrónico en ninguno de los dos.
   - El dataset de Contratos SÍ trae: representante legal (nombre, tipo/núm. documento,
     nacionalidad, género, domicilio), supervisor (nombre+doc), ordenador del gasto y de
     pago (nombre+doc), datos bancarios (banco, tipo de cuenta, número de cuenta),
     dirección de ejecución. Es público por Ley 1712/2014, pero es dato personal
     identificable — usar para verificar una contraparte puntual, no para compilar
     listas de contacto masivas sin más cuidado.
   - Lectura de PDFs adjuntos (`secop_playwright.py`): probado en vivo, SIGUE bloqueado
     por el muro de validación anti-bot de Vortal (community.secop.gov.co) — no devuelve
     contenido real, solo la pantalla de captcha. No se debe intentar sortear esa
     protección. Confirma la limitación ya documentada en README.md.

### Método de trabajo validado (usar en el futuro)
- Para consultas puntuales de datos: usar `sodapy`/Socrata directo con agregaciones
  SoQL (`select=... count(*)/sum(...)`, `group=`) en vez de traer todos los registros
  cuando se puede — más rápido y barato.
- Para reportes grandes (cientos/miles de registros): el script Python escribe el
  `.md` **directo a disco**, nunca se ensambla el contenido completo dentro del
  contexto de Claude — así el costo en tokens no escala con el tamaño del reporte.
- Para pasar `.md` → `.docx`: usar `pandoc` (ya instalado en el sistema) con un solo
  comando (`pandoc input.md -o output.docx --toc`). Cero necesidad de leer o
  reescribir el contenido para convertirlo.
- Sin `SOCRATA_APP_TOKEN` las consultas funcionan pero con throttling notorio —
  considerar agregar uno a `.env` si esta investigación puntual se vuelve recurrente.

### Próximos pasos posibles (no confirmados, solo propuestos)
- Enriquecer el informe de Nasa Kiwe y el ranking de obras con representante legal /
  supervisor / banco (dato ya disponible en el JSON crudo para Nasa Kiwe, sin costo
  extra; para el top 50 de obras faltaría una consulta agrupada adicional).
- Evaluar agregar a Corporación Nasa Kiwe como entidad monitoreada aparte (ver punto 1).

---

## DECISIONES DE DISEÑO TOMADAS
- Haiku para scoring (económico, batches de 8)
- Sonnet para documentos (calidad jurídica colombiana)
- Prompt caching en system prompt del scorer
- Deduplicación por id_proceso en SQLite
- Retry exponencial Socrata: 3 intentos (5s, 10s, 20s)
- Field aliases para manejar variaciones en nombres de campos de Socrata
- Documentos: campos sin datos reales = [COMPLETAR], nunca inventa

---

## AUDITORÍA HECHA — PENDIENTES IDENTIFICADOS
Prioridad acordada:
1. ✅ Dashboard web (próximo paso)
2. Alertas de fecha límite de cierre de proceso
3. SECOP I + Contratación Directa (más oportunidades)
4. Tracking de postulaciones (CRM básico)
5. Multi-usuario

Items descartados por ahora: WhatsApp (Telegram está bien), email
