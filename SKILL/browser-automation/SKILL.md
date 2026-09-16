---
name: browser-automation
description: Protocolo de disciplina para automatización de navegador con Claude Code. Aplica a cualquier tarea que controle un browser — testing E2E, scraping, formularios web, sesiones con login, monitorización de webs, automatización en redes sociales, comparativa de precios, generación de leads, QA de landings, tests de regresión visual. Activación automática al detectar Playwright, Puppeteer, Selenium, Chrome DevTools Protocol (CDP), browser-use, scraping, headless browser, o cualquier intención de "automatiza la web", "controla el navegador", "extrae datos de [sitio]", "rellena formularios", "haz tests de [web]", "monitoriza precios", "genera leads".
---

# Browser Automation — Protocolo de disciplina

Estas son las reglas que debes seguir SIEMPRE que automatices un navegador. No son sugerencias — son tu protocolo de trabajo. Están extraídas de problemas reales que aparecen una y otra vez.

---

## A. Seguridad y credenciales (las más importantes)

### A1. Anticipa la pregunta de seguridad ANTES de que el usuario la haga

Si vas a abrir un browser donde el usuario tendrá que meter credenciales (Google, Skool, LinkedIn, etc.), **antes** de pedirle que se loguee, lista explícitamente las garantías de seguridad:

- Si es Chrome real (firmado por Google) o Chromium for Testing
- Si tiene flag `--enable-automation` activo (banner de automation visible) o no
- Dónde escucha el puerto de CDP (loopback `127.0.0.1` vs LAN/público)
- Dónde se guardan las cookies (Keychain del SO vs disco plano)
- Si la sesión es desechable (carpeta temporal) o persistente (perfil dedicado)
- Si está en modo `codegen`/`record` (puede loggear keystrokes) o no

El usuario no debería tener que preguntarte "¿es seguro?". Tú deberías habérselo dicho ya.

### A2. NUNCA pidas login en Chromium for Testing

Si lanzas el browser con `playwright open`, `playwright codegen`, o cualquier comando que arranque **Chromium for Testing** con `--enable-automation`:

- **No le pidas al usuario que se loguee ahí.**
- Google detecta el flag y puede bloquear el login o flagear la cuenta.
- El perfil suele estar en `/var/folders/.../tmp/` y se borra al cerrar.

Si necesitas sesión persistente con login → cambia a la ruta de Chrome real con perfil dedicado (regla A3).

### A3. Perfil dedicado, NUNCA el perfil personal del usuario

Para sesiones persistentes con login real (YouTube, Skool, etc.):

- **Siempre usa perfil dedicado** en una carpeta del proyecto (ej: `.chrome-profile/`).
- **Nunca uses el perfil personal del usuario** (`~/Library/Application Support/Google/Chrome/Default`):
  - Lockfile colisiona si Chrome personal está abierto
  - Google detecta automatización en el perfil principal y puede flagear la cuenta
- Loguear UNA VEZ en el perfil dedicado = sesión persiste para siempre.

### A4. CDP siempre en localhost — flags obligatorios

Cuando lances Chrome con Chrome DevTools Protocol:

```
--remote-debugging-address=127.0.0.1
--remote-allow-origins=http://localhost:9222
```

Razón: por defecto el puerto se abre en todas las interfaces (incluido LAN). Cualquiera en la misma red podría conectarse.

Y avisa al usuario: cualquier proceso del Mac puede teóricamente conectarse a `:9222` mientras el browser esté abierto. Cerrar la ventana = liberar puerto.

### A5. Recuerda al usuario el checklist de uso seguro

Tras configurar un setup con login real, lista una vez:

1. Loguear solo en el browser dedicado, nunca en `playwright open`/`codegen`
2. Cerrar la ventana al terminar (libera puerto CDP)
3. Verificar `git status` antes de `git add` (que no entren `.chrome-profile/`, `leads/`, `.env`)
4. No subir cookies/auth state a Drive ni a ningún cloud
5. Activar 2FA en cuentas críticas
6. No correr scripts que no haya leído

---

## B. Configuración del browser

### B1. Modo headed durante desarrollo

En la primera sesión de un proyecto, lanza el browser en modo **headed** (visible). Razón: el usuario necesita ver qué hace el bot para darte feedback visual rápido si algo falla.

Cambia a headless solo si:
- El usuario lo pide explícitamente
- Es una tarea programada (scheduled task / routine)
- El test ya está validado y se ejecuta autónomamente

### B2. Verifica CDP antes de continuar

Tras lanzar Chrome con CDP, **antes de hacer cualquier otra cosa**, verifica:

```
curl http://127.0.0.1:9222/json/version
```

No asumas que está corriendo solo porque ejecutaste el comando. El usuario puede haber abierto Chrome desde el Dock pensando que estaba bien, y el flag de CDP no estará activo. La verificación tarda 1 segundo y evita errores en cadena.

### B3. Cuidado con falsos positivos en headless

Cuando un test en modo headless reporte errores de **Google Analytics, Tag Manager o Ads**, sospecha falso positivo: Google bloquea el tracking si el User-Agent contiene "HeadlessChrome".

Antes de reportar como bug del cliente:
- Repite el test en modo headed
- Si en headed pasa, marca como falso positivo y repórtalo separado

### B4. Screenshots con timestamp organizados

Todos los screenshots:
- Carpeta `/screenshots/` o `/playwright-report/screenshots/` dentro del proyecto
- Nombre: `YYYY-MM-DD_HH-MM-SS_descripcion.png`
- Descripción del contenido, no `screenshot1.png`

---

## C. Higiene del proyecto

### C1. .gitignore obligatorio antes del primer commit

Añade al `.gitignore` desde el setup inicial (no después):

```
.chrome-profile/
node_modules/
playwright-report/
test-results/
leads/
.env
*.session.json
```

Verifica con `git status` antes de cualquier `git add` que ninguno de estos aparezca.

### C2. MCPs requieren reinicio

Si añades un MCP nuevo a `.mcp.json` (Playwright MCP, Airtable MCP, etc.), **recuerda al usuario** que tiene que reiniciar Claude Code para que se cargue. No empieces a usar el MCP sin verificar primero que está activo.

### C3. Antes de scrapear, comprueba el sitio

- Revisa el `robots.txt` del dominio (`https://[dominio]/robots.txt`)
- Si bloquea la sección que quieres scrapear → avisa al usuario
- Si los términos de servicio prohíben scraping comercial → avisa
- Para datos personales, recuerda al usuario que aplica el RGPD en Europa

No bloquees al usuario por esto — solo informa una vez por sesión y deja que él decida.

---

## D. Selectores y robustez

### D1. Selectores con fallback

Cuando un selector CSS o XPath falla:

1. **Intento 1**: el selector original con timeout de 5s
2. **Intento 2**: variante alternativa (ej: cambiar `#submit-btn` por `[type="submit"]`, o usar `text=...`)
3. **Intento 3**: snapshot del DOM y búsqueda por texto visible
4. Si todo falla → captura screenshot de evidencia y pide ayuda al usuario

Nunca repitas el mismo selector 5 veces esperando que funcione.

### D2. Evita `function nombrada(){}` en `page.evaluate()`

Bug conocido: declarar funciones nombradas dentro de `page.evaluate()` puede dar `__name is not defined` por la transformación de TypeScript/esbuild.

Workaround: usa IIFE (`(() => { ... })()`), funciones flecha asignadas a const, o escribe el flujo de forma iterativa sin declaraciones de función.

### D3. Verificación post-acción robusta (DOS señales)

Después de hacer submit (responder un comentario, mandar un formulario, dar like), verifica el resultado de **al menos dos formas**:

- Verificar que el textarea se vacía o desaparece
- **Y además** comprobar que el contenido nuevo aparece en el DOM (buscar el comentario nuevo en el thread, etc.)

Si solo verificas con una señal, puedes tener falsos negativos: el script reporta error pero la acción sí se ejecutó. Esto es peor que un fallo limpio porque el usuario no sabe si reintentar.

### D4. Cierra siempre el browser

- `page.close()`, `context.close()`, `browser.close()` al final de cada test/script
- Usa `try/finally` para garantizar el cierre incluso si el script falla
- No dejes browsers huérfanos consumiendo memoria

---

## E. Acciones públicas (cero autopilot sin permiso)

### E1. Volumen real ANTES de empezar

Si la tarea va a operar sobre N elementos (felicitar wins, responder comentarios, dar likes), **calcula N primero y avísale al usuario** antes de empezar.

Ejemplo real: una sección de "wins" de Skool puede tener 19 páginas × 30 posts = 570 items. Felicitar 570 con comentario automático = spam evidente, daño reputacional + posible ban de la plataforma.

Pregunta siempre 3 cosas:
- **Alcance**: ¿todos / última semana / primera página / N concretos?
- **Personalización**: ¿mensaje plantilla o personalizado por LLM por cada item?
- **Duplicados**: ¿saltamos los que ya tengan tu interacción previa?

### E2. Drafts antes de publicar — pregunta tono

Cualquier contenido público (comentarios, replies, posts, DMs) debe pasar por el flujo:

1. Genera drafts
2. Muéstraselos al usuario en una tabla legible
3. Pregunta tono / cadencia / si aprueba
4. Aplica correcciones específicas si las pide ("el #1 no le digas hermano")
5. SOLO entonces publica

Nunca publiques sin draft revisado, aunque el usuario diga "responde a todos".

### E3. Dry-run con 1 antes del batch

Para operaciones masivas, **siempre** prueba con UNO primero:

1. Manda solo el item #1
2. Verifica el resultado (regla D3 — dos señales)
3. Si funciona → continúa con el resto
4. Si falla → diagnostica antes de seguir

El comportamiento puede ser distinto en uno vs muchos. Si haces batch directo y falla en el #50 con cosas ya publicadas, es un caos.

### E4. Cadencia humana entre acciones

Entre acciones públicas (likes, comentarios, replies, follows), espera **30-60 segundos** aleatorios. Razón:

- Los algoritmos de plataformas detectan ráfagas
- Skool, LinkedIn, Instagram tienen rate limits no documentados
- El daño de un baneo es peor que el ahorro de tiempo

### E5. Sitios anti-bot agresivo: avisa primero

Si el usuario pide automatizar uno de estos sitios conocidos:

- LinkedIn (en scraping masivo)
- Amazon
- Instagram, TikTok
- Sitios de banca / fintech

Avisa antes: *"Este sitio tiene protección anti-bot fuerte. Es probable que detecte y bloquee la automatización tras pocos intentos. ¿Quieres continuar igual?"*

### E6. ToS de redes sociales — el usuario decide

Para automatización en redes sociales (LinkedIn, X, Instagram, Facebook, TikTok, YouTube), **recuerda al usuario** que la mayoría de plataformas prohíben automatización en sus Términos de Servicio y que el incumplimiento puede causar baneo.

No te niegues a hacerlo (es decisión del usuario), pero asegúrate de que sabe el riesgo antes de empezar.

### E7. Datos personales: aviso RGPD

Si la tarea implica extraer datos personales de personas reales (emails, teléfonos, nombres), recuerda una vez:

> *"Esto va a procesar datos personales. En Europa aplica el RGPD: necesitas base legal para tratarlos y los sujetos tienen derecho de acceso/borrado. Consulta con un abogado si vas a usarlo comercialmente."*

Tras el aviso, sigue con la tarea.

---

## F. Sesiones con login

### F1. Pregunta el método al primer login

Cuando el usuario pida automatizar una plataforma con login (Skool, LinkedIn, Notion, GitHub, etc.), **pregunta cuál de las opciones prefiere**:

- **Opción A — Chrome dedicado con perfil**: lanzas Chrome real con `--user-data-dir=.chrome-profile/`. Login una vez = persistencia.
- **Opción B — `state-save`/`state-load`**: lanzas browser limpio, esperas a que el usuario haga login, guardas la sesión a JSON.
- **Opción C — MCP `--extension`**: el Playwright MCP en modo extensión engancha al Chrome real del usuario.

No asumas. Pregunta la primera vez y documenta la elección en CLAUDE.md.

### F2. Verifica la sesión antes de continuar

Cuando el usuario diga *"ya estoy logueado"*, no des por hecho que la sesión está activa para tu script. Verifica:

- Lista pestañas abiertas en el browser
- Comprueba cookies de auth (`auth_token`, `SID`, `LOGIN_INFO`, etc.)
- Si la sesión no aparece donde esperas → diagnostica antes de seguir

---

## G. Reporte final

### G1. Informe estructurado al terminar

Al finalizar cualquier tarea de browser automation, genera un resumen breve con:

- ✅ **Qué se ejecutó correctamente**
- ⚠️ **Estado ambiguo** (cosas que se enviaron pero no se pudo verificar — esto es crítico)
- ❌ **Lo que falló** (con razón concreta y screenshots)
- 📁 **Archivos generados** (screenshots, JSONs de leads, etc.)
- 🔄 **Sugerencias para mejorar el SKILL.md** si el patrón puede convertirse en regla nueva

### G2. Honestidad sobre el estado ambiguo

Si una acción se mandó pero no pudiste verificar el resultado (regla D3 falló), **dilo claramente**:

> *"⚠️ Estado ambiguo: el script clicó submit pero no pude verificar si la respuesta llegó a publicarse. Verifica manualmente antes de continuar con el resto."*

Nunca asumas éxito sin señal verificable. Es preferible una alerta honesta a un falso positivo que el usuario descubre después.

---

## Cómo se invoca esta skill

Esta skill se carga **automáticamente** cuando detectas que el usuario está trabajando en browser automation (keywords del frontmatter `description`). También puede invocarse manualmente con `/browser-automation`.

Una vez cargada, sigue las reglas como protocolo durante toda la sesión.

---

## Origen de las reglas

- A1, A2, A3, A4, A5: extraídas de proyecto real donde el usuario preguntó repetidamente "es seguro meter mis credenciales aquí" antes de configurarlo bien
- B2: extraída de caso real donde Chrome se lanzó desde el Dock sin CDP activo
- B3: extraída de test que reportó 6 falsos positivos por bloqueo de Google Analytics en headless
- C1: extraída de proyecto donde casi se commitea `.chrome-profile/` con cookies de Google
- D2: extraída de bug `__name is not defined` con esbuild
- D3: extraída de caso real donde `reply.ts` reportó error pero la respuesta YouTube sí se publicó
- E1: extraída de Skool con 570 wins históricos (felicitar todos = spam evidente)
- E2: extraída de "el #1 no le digas hermano" — el tono importa
- E3: extraída de "manda solo el #1 como prueba"
