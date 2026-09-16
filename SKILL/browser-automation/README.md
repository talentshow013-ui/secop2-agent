# browser-automation skill

Skill personal para Claude Code que activa un protocolo de 10 reglas cuando trabajas con automatización de navegador (Playwright, browser-use, scraping, sesiones con login, etc.).

**Hecha por [Juanpe — Divisual Project](https://www.youtube.com/@juanpe.divisual)**

## Qué hace

27 reglas agrupadas en 7 secciones que activan disciplina sistemática cuando Claude Code automatiza un navegador. Las reglas se cargan **solo cuando son relevantes** — en proyectos no-browser: 0 tokens consumidos.

## Para qué sirve (cualquier tarea de browser automation)

Aunque la skill se construyó a partir de proyectos reales con Playwright + Chrome DevTools Protocol, las reglas aplican a **cualquier caso**:

- **Testing E2E** de webapps tuyas o de clientes
- **Scraping** de cualquier tipo (precios, listings, leads, papers)
- **QA automatizado de landings** — detección de bugs, errores de consola, problemas de performance
- **Monitorización web** — comprobar uptime, cambios en contenido, alertas
- **Lead generation** — extracción de contactos de directorios públicos
- **Form filling masivo** — formularios gubernamentales, encuestas, aplicaciones
- **Automatización en plataformas con login** — Skool, YouTube Studio, LinkedIn, Notion, GitHub
- **Comparativa de precios** entre e-commerce
- **Reportes automatizados** — extraer dashboards (Stripe, Analytics) sin API
- **Tests de regresión visual** — capturas en distintos breakpoints

## Las 7 secciones

| Sección | Reglas | Cuándo se activa |
|---|---|---|
| **A. Seguridad y credenciales** | 5 reglas | Siempre que haya login real |
| **B. Configuración del browser** | 4 reglas | En todos los casos |
| **C. Higiene del proyecto** | 3 reglas | Setup inicial + scraping |
| **D. Selectores y robustez** | 4 reglas | Siempre |
| **E. Acciones públicas** | 7 reglas | Cuando publicas/interactúas en plataformas |
| **F. Sesiones con login** | 2 reglas | Solo si hay autenticación |
| **G. Reporte final** | 2 reglas | Al terminar cada tarea |

**Lo más importante:** la skill solo se carga cuando es relevante. En proyectos donde no hagas browser automation, **0 tokens consumidos**.

## Instalación

### Opción A — copiar a tu carpeta personal de skills

```bash
mkdir -p ~/.claude/skills/browser-automation
cp SKILL.md ~/.claude/skills/browser-automation/SKILL.md
```

A partir de ahora, en cualquier proyecto donde abras Claude Code y trabajes con browser automation, la skill se activará sola.

### Opción B — copiar como skill de proyecto

Si solo quieres usarla en un proyecto específico (no global):

```bash
mkdir -p .claude/skills/browser-automation
cp SKILL.md .claude/skills/browser-automation/SKILL.md
```

## Verificar que funciona

Abre Claude Code en cualquier proyecto y pregunta:

```
What skills are available?
```

Deberías ver `browser-automation` en la lista. Si no aparece, reinicia Claude Code (la primera vez que añades una skill nueva, hace falta reiniciar — los cambios posteriores se detectan en caliente).

Para invocarla manualmente:

```
/browser-automation
```

Para activación automática, pídele a Claude algo de browser automation:

```
Crea una landing y prueba el formulario con Playwright
```

Claude detectará el contexto y cargará la skill.

## Personalización

El `SKILL.md` es texto plano. Puedes editarlo para añadir tus propias reglas, eliminar las que no te aplican, o ajustar el tono.

Si modificas el archivo, los cambios se aplican en la siguiente sesión sin necesidad de reinstalar.

## Licencia

MIT — úsala, modifícala, redistribúyela.

## Más skills, más vídeos

Si te ha gustado, en [La Tribu Divisual](https://www.skool.com/divisual) compartimos skills, agentes y workflows nuevos cada semana.
