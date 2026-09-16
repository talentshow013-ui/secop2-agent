# research/ — scripts de investigación ad-hoc sobre SECOP II

Scripts usados desde Claude Code (no desde el bot) para inteligencia de mercado.
Escriben resultados a disco (JSON en la ruta que se pasa como argumento y/o `.md` en `output/`)
para no cargar el contexto del modelo con miles de registros. Ejecutar desde la raíz del proyecto
con el venv activo; leen `SOCRATA_APP_TOKEN` de `.env`.

| Script | Qué hace | Uso |
|---|---|---|
| `buscar_procesos.py` | Busca procesos en `p6dx-8zbt` por palabras clave (editar `where`), imprime conteos por estado/fase/modalidad y guarda el crudo | `python research/buscar_procesos.py salida.json` |
| `proponentes_por_entidad.py` | Dado el JSON anterior, trae de `hgi6-6wh3` todos los proponentes de esas entidades (cruce por `nit_entidad`) | `python research/proponentes_por_entidad.py procesos.json proponentes.json` |
| `perfil_competidor.py` | Para un NIT de proveedor: todo lo que ha ofertado, quién más ofertó en esos procesos, y el mercado del segmento (editar NIT y filtro) | `python research/perfil_competidor.py salida.json` |
| `perfil_proveedor.py` | Para un NIT: ofertas + rivales, procesos adjudicados (precio base vs adjudicado), precio base por entidad, contratos firmados | `python research/perfil_proveedor.py salida.json` |

Los scripts están escritos para el caso "concesiones de alumbrado público" (sept-2026); para otro
tema se cambian las cláusulas `where` — la estructura de cruce entre datasets es la reutilizable.
Ver `CLAUDE.md` para los datasets y sus trampas.
