---
type: guide
title: Usar Camarón
description: Cómo se usa Camarón en el día a día — instalarlo, el primer arranque, unirte a un equipo, documentar unidad a unidad, revisar, compartir, el tablero, la salud, mantener la documentación al día y empezar de nuevo — primero en la app de escritorio y después con el comando que hace lo mismo.
tags: [onboarding, workflow]
x-owner: human
---
# Usar Camarón

> **TL;DR:** Instala el kit, ejecuta `camaron app` y elige la carpeta con tus repos. La primera pasada no necesita IA.
> Después deja que tu agente documente una unidad cada vez (o varias a la vez), revisa en el portal lo que escribió,
> confirma lo que está bien y compártelo con el equipo. Cuando cambia el código, el kit te dice qué páginas se quedaron
> atrás.

## La idea en un minuto

Camarón es un **cerebro del proyecto**: un único sitio versionado, `cam-docs/`, donde el código, la arquitectura, el
dominio y las decisiones de un proyecto con varios repos quedan explicados para personas y para agentes de IA.

1. **Instalar ya da valor, sin IA.** El kit detecta tus repos y escribe, con análisis estático, la página de inicio del
   proyecto, una página por repo (endpoints, datos, estados, mensajes, variables de entorno), las librerías y sus
   vulnerabilidades conocidas, un primer borrador C4 y el plan.
2. **Después la IA lo completa**, una **unidad** de trabajo por sesión: el descubrimiento de cada repo, las entrevistas,
   la arquitectura, el dominio, los datos, los flujos, las decisiones, las traducciones.
3. **Todo lo que escribe la IA se puede revisar**: es un borrador hasta que una persona lo confirma, lleva el código del
   que sale (`x-sources`) y pasa a sospechoso en cuanto ese código cambia.

Tres formas de entrar, los mismos comandos debajo: la **app de escritorio** (`camaron app`) para operar, el **portal**
para leer y revisar, y la **terminal** (`camaron`, el asistente, o cualquier comando) para todo, scripts y CI incluidos.

<!-- tour:app -->

## Primer arranque

**Requisitos:** git y Node.js 22 o superior; `uv` (lo instala el lanzador); Claude Code o Codex con sesión iniciada
para las sesiones con IA (también sirven OpenCode y Gemini CLI). Docker es opcional.

**Instala el kit una vez por máquina**, en una línea y sin clonar nada:

```sh
curl -fsSL https://raw.githubusercontent.com/iandelu/camarones-documenter/main/install-global.sh | sh
```

En Windows, la línea de PowerShell del README hace lo mismo. El comando `camaron` queda en tu PATH.

**Abre la app** en la carpeta que agrupa tus repos, o en cualquier otra:

```sh
camaron app
```

La primera vez descarga Electron (unos 100 MB) en `~/.camarones/desktop`. **Elegir carpeta**, mira lo que ha encontrado,
**Continuar** y sigue el asistente de primer arranque: repos, herramientas, instalar, stack, un primer borrador de
arquitectura y listo. Terminas en el **Resumen**, con el siguiente paso. ¿Prefieres la terminal? `camaron` en esa
carpeta abre los mismos pasos en el asistente; puedes cambiar de uno a otro a medias.

<!-- go:flow -->

## Unirte a tu equipo

Si tu equipo ya tiene un repo `cam-docs`, las dos puertas de la pantalla de inicio de la app llegan a él: **Elegir
carpeta** sobre tus repos pregunta si el equipo ya tiene su documentación en un repo `cam-docs` (responde **Sí** y pega su
URL), y **Unirme a la documentación de mi equipo** pide la URL y después la carpeta donde están tus repos. Desde una
terminal: `camaron join <url> [carpeta-de-tus-repos]`. El kit lo clona, o reutiliza la copia que ya tienes, y solo
prepara tu máquina: el equipo ya eligió los repos, el stack, la arquitectura y el plan, unirte no cambia nada de eso, y
las sesiones siguen donde se quedaron. Los repos se reconocen por su remoto, no por el nombre de la carpeta: un clon que
tienes con otro nombre se enlaza con el nombre del equipo en vez de clonarse otra vez. Dejar fuera una herramienta al
unirte solo afecta a tu máquina.

Lo que llegó con el repo del equipo y ejecuta código o guía a los agentes (hooks, servidores MCP, ajustes, skills,
plugins) espera a que lo apruebes en tu máquina: **Ajustes › Confianza**, o `camaron trust`.

<!-- go:settings/trust -->

## Un día normal

1. **Mira el siguiente paso**: el **Resumen** de la app, o `camaron plan next`.
2. **Haz una unidad con tu agente**: **Empezar con Claude Code** (o Codex) la abre como una terminal en el lienzo del
   Plan, solo con esa unidad, y ahí le escribes al agente. Ciérrala cuando quieras: la unidad queda en pausa y
   **Seguir** retoma la conversación.
3. **O haz varias a la vez**: **Plan › Ejecutar las listas** (`camaron run --parallel 2`), cada unidad en su propia
   copia de `cam-docs`, que se fusiona al terminar. El **Piloto automático** (`camaron autopilot`) va una a una, sin
   vigilancia.
4. **Lee y revisa** lo que escribió: **Ver portal** y después Revisión.
5. **Sube**: **Docs › Subir cambios** o `camaron push` (o **Sincronizar**, `camaron share`, para traer y subir).

Cada unidad termina con un commit local en `cam-docs` y una nota de relevo, así que la siguiente sesión —tuya o de un
compañero— sabe qué se comprobó, qué no y qué viene después.

<!-- go:plan -->
<!-- tour:plan -->

## Revisar y confirmar

Los borradores de la IA son útiles pero no están verificados. En el portal:

- **Revisión** lista lo que espera a una persona: borradores, páginas por reconfirmar, revisiones que espera un agente.
  Marca varias y **Confirmar las n**.
- En una página, **Confirmar como correcta** la firma con tu nombre: desde ese momento los agentes la tratan como la
  verdad.
- **Pedir un cambio** deja un comentario para la siguiente sesión de IA (o crea un elemento del tablero con la página
  enlazada).
- **Editar** la cambia tú; una página confirmada que editas hay que reconfirmarla.

Desde una terminal: `camaron confirm <página> --by <nombre>`, `camaron feedback <página> "<qué está mal>" --by <nombre>`,
`camaron status`.

<!-- portal:#/review -->

## Trabajar con el equipo

`cam-docs` es un repo git normal. Al abrir un proyecto —la ventana de la app de escritorio o el asistente de la
terminal— se trae solo el trabajo del equipo y nunca se sube nada. Si los cambios del equipo chocan con los tuyos, no
toca nada y dice qué ficheros; sin conexión, el proyecto se abre igual y avisa de que trabajas con lo último que
trajiste. Tras traer, el explorador C4 se reconstruye solo si estaba desactualizado, y los grafos de código de los repos
cuyo HEAD se movió se reconstruyen en segundo plano en la app (el asistente de la terminal solo dice cuántos hay
desactualizados; los rehace `camaron pull`).

Los checkpoints se quedan en local y subir es un paso que das tú, con tres acciones en la franja del equipo de **Docs** (la app),
**Plan › Sincronizar** (el portal) y **🤝 Equipo: traer, subir o sincronizar** (el asistente de la terminal):

- **Traer cambios** (`camaron pull`): el trabajo del equipo rebasado dentro; lo tuyo no se sube.
- **Subir cambios** (`camaron push`): un checkpoint y después lo tuyo subido. Se niega si el equipo tiene cambios
  nuevos: tráelos primero, o sincroniza con el equipo.
- **Sincronizar** (`camaron share`): traer y después subir.

Una línea dice cuánto os separa (n por traer · m por subir · última vez …) y la acción útil es el botón principal.
**Subir al guardar** (`camaron share --auto on`) sube tras cada checkpoint, solo en esta máquina. Un conflicto se
deshace sin tocar nada; algo que parece un secreto nunca se sube.

¿Aún no hay repo del equipo? Pega su URL en **Docs › Repo del equipo** (`camaron remote <url>`); tu primera subida lo
publica.

## El tablero y las historias

El tablero vive en `cam-docs/backlog/`, junto a la documentación, y Backlog.md puede leerlo. Actívalo con **Tablero ›
Activar el tablero** (`camaron board init`).

- **Escribe una historia** en las **Historias** del portal: *Como / quiero / para*, los ficheros y páginas que toca, un
  veredicto INVEST y subtareas en **oleadas** que nunca tocan los mismos ficheros. No se guarda nada hasta que lo
  apruebas.
- **Mueve tarjetas** en el Tablero de la app o en el del portal. Pasar a En curso comprueba antes dependencias y
  choques.
- **Lo que puede empezar ya**, para un agente o una persona: `camaron board next --n 3`; el trabajo abierto en oleadas:
  `camaron board waves`.

<!-- go:board -->
<!-- portal:#/stories -->

## Salud, librerías y vulnerabilidades

**Calidad**, en la app, es la salud del proyecto sin IA —máquina, documentación y código— con un veredicto, un estado
por área y una fila por repo (puerta de calidad de SonarQube, cobertura, vulnerabilidades, deuda). **Comprobar todo** la
recalcula (`camaron health --refresh`). Una herramienta que falta tiene ahí su botón **Instalar**.

**Librerías** (la segunda vista de Calidad, `#/quality/libs`) lista cada dependencia con la versión que usan los repos. **Buscar vulnerabilidades** las compara con la
base de datos sin conexión de OSV (`camaron inventory --cves`; nada sale de tu máquina). **Buscar versiones nuevas**
pregunta a los registros públicos la última versión estable de cada una (`camaron inventory --latest`; salen de tu
máquina los nombres de las librerías, nunca las vuestras). **Actualizar ▾** propone la última versión, o la que corrige
sus avisos, y crea una rama en ese repo (`camaron bump`), sin commit ni push; en un módulo Maven cambia el pom padre
del mismo repo, que es donde está la versión.

SonarQube: guarda un token en **Ajustes › Tokens** y la comprobación de salud lee la puerta de calidad, la cobertura y
los problemas de cada repo.

<!-- go:quality -->
<!-- go:quality/libs -->

## Mantener la documentación al día

Cuando el código se mueve, la documentación lo sigue:

- `camaron changes` lista lo que cambió en los repos desde que se escribió la documentación; **Plan › Mantenerla al
  día** abre una sesión que actualiza las páginas afectadas.
- **Calidad › Páginas desactualizadas** (`camaron fresh`) lista las páginas cuyo código citado cambió o desapareció;
  **Sigue valiendo** da una por buena y **Añadir una unidad que las actualice** pone el trabajo en cola.
- En CI, `camaron ci` escribe un job por repo de servicio que comenta en cada pull request qué páginas deja
  desactualizadas, sin IA; `camaron pr propose <url>` deja que un agente proponga los cambios de la documentación en
  una PR de `cam-docs`.
- `camaron check` es la puerta: enlaces rotos, diagramas que no se dibujan, secretos, estructura.

## Programar con Camarón

Abre Claude Code o Codex en el espacio de trabajo y pídele un cambio: el agente empieza la skill `cam-task` (y detrás
`cam-difficulty`, `cam-verify`, `cam-ship` y `cam-retro`), cuyo primer paso es `camaron change start`: el cambio va en su
propia rama, `cam/<id>-<slug>`, en cada repo de servicio, y la documentación en su propio worktree de `cam-docs`
(`.cw/<id>`); tu checkout de `cam-docs` y su tablero nunca cambian de rama. Cada paso apunta su fase
(`camaron change phase`).

- **Primero la documentación.** El agente lee `cam-docs` y resume lo que dice, con citas, antes de tocar código.
- **Dificultad.** Baja (0–2), media (3–5) o alta (6+). A una baja le toca un plan corto, a una media un plan que
  apruebas tú, a una alta una especificación, un plan y una propuesta de partirla en elementos de tablero en borrador.
- **Prueba primero y luego verificación.** El agente ejecuta el build, los tests y los linters del propio repo más
  `camaron check`.
- **Guardarraíles e impacto.** Rutas prohibidas, gitleaks, páginas que el cambio deja desactualizadas
  (`camaron pr fresh`) y reglas de confianza; después, el impacto en la documentación, los contratos y el tablero.
- **Una sola pregunta.** «¿Abro las PR?» Si dices que sí, abre una PR de código en borrador por repo y una PR de
  documentación en borrador, enlazadas entre sí, y las apunta en el cambio (`camaron change link`). El kit nunca
  fusiona. El agente mueve su propia tarjeta con los comandos del cambio: a In Progress con `camaron change start`, a
  In Review con el primer `camaron change link`; Done es tuyo: `camaron change close` la mueve cuando ya fusionaste
  (`--abandon`: vuelve a Ready).

Con superpowers instalado, sus skills de brainstorming, planes, TDD y depuración se usan en esos pasos, dentro de las
ramas y el worktree del propio cambio.

Para adaptar el flujo a tu equipo:

- `camaron skills list` muestra de dónde viene cada skill (kit, equipo, solo del equipo) y si la versión del kit cambió
  desde tu copia. `fork NOMBRE` crea una copia del equipo, `diff NOMBRE [--kit]` enseña lo que cambiaste y
  `reset NOMBRE` vuelve a la del kit (tu copia queda en `.camarones/skills/.reset/`).
- Una copia del equipo vive en `cam-docs/.camarones/skills/<nombre>/`, gana a la del kit y sobrevive a las
  actualizaciones. Cada máquina aprueba una copia editada una vez en `camaron trust`, y `camaron doctor` avisa cuando la
  versión del kit de una skill bifurcada ya se movió.
- Las lecciones entran como notas: `camaron skills note SKILL TEXTO --source retro|review|board`, y se leen con
  `camaron skills notes [SKILL]`. Viven en `docs/.work/skill-notes/`.
- Cada skill tiene dos interruptores. `camaron skills disable|enable NOMBRE` la apaga o la enciende para todo el
  proyecto (`skills: {off: [...]}` en `workspace.yaml`; deja de copiarse a `.claude/` y `.agents/`); con `--machine`
  la apagas solo para ti (una regla `Skill(NOMBRE)` en el `.claude/settings.local.json` local de Claude Code: el agente
  deja de usarla, escribir `/NOMBRE` aún la llama y los ficheros del equipo no cambian).
- Packs opcionales de skills, apagados hasta que alguien los añade: `camaron skills add ponytail` (el cambio más
  pequeño que resuelve la tarea, más revisión y auditoría; MIT) y `camaron skills add impeccable` (diseño frontend;
  Apache-2.0; su lanzador descarga un binario verificado la primera vez que se usa). Cada uno se descarga en el commit
  que fija el kit, se copia con su licencia en `.camarones/skills/`, queda anotado en `.camarones/skills.lock` y cada
  máquina lo aprueba una vez en `camaron trust`; `camaron skills remove PACK` lo quita (una carpeta que el equipo
  editó se queda).

`camaron change` lleva las cuentas del cambio, sin IA, y guarda su registro en esta máquina
(`.camarones/.cache/changes/<id>.json`):

- `camaron change start "<título>" --item WI-n` lo comprueba todo antes (los repos están y no tienen trabajo sin
  confirmar, la tarjeta puede empezar) y después crea la rama en cada repo (los repos de la tarea, o `--repo`; si ya
  tienes una rama de trabajo limpia, la adopta), abre el worktree de la documentación, mueve la tarjeta a
  **In Progress** y lista la documentación que leer, con su confianza (`--files repo:ruta` añade las páginas que citan
  esos ficheros). Si no puede empezar, dice por qué; `--force` lo empieza igualmente.
- `camaron change phase [ID] FASE` sigue los pasos (`docs`, `assess`, `plan`, `code`, `docs-update`, `verify`, `ship`,
  `retro`), solo hacia delante; `camaron change status` enseña cada cambio abierto y su siguiente paso.
- `camaron change link [ID] URL [--repo NOMBRE|docs]` apunta una PR: la tarjeta pasa a **In Review**.
- `camaron change close ID` comprueba con git que cada rama está fusionada en su base: la tarjeta pasa a **Done**.
  `--abandon` la devuelve a **Ready**. Los dos quitan el worktree de la documentación; las ramas se quedan.

El ID se puede omitir dentro de la rama de un cambio o cuando solo hay uno abierto. Los guardarraíles y abrir las
propias PR llegan en versiones posteriores.

## Costes y KPIs

- **Plan › Plan desde 0** (`camaron plan cost`): tokens, horas y dólares equivalentes de la API que se llevó el plan,
  para todo el equipo, por fase y por unidad.
- **Calidad › KPIs** en el portal (`camaron kpis`): proporción confirmada, páginas desactualizadas, búsquedas sin
  respuesta, coste de IA por mes y las preguntas que nadie encontró; un clic convierte cada una en pregunta abierta
  para la siguiente entrevista.
- **Preguntas de oro** (`camaron eval`): preguntas que la documentación tiene que poder responder, aprobadas por una
  persona, que se le hacen a un agente que solo puede leer la documentación. **Con y sin cam-docs** (`camaron ab`) hace
  la misma pregunta dos veces para enseñar lo que ahorra la documentación.

<!-- portal:#/kpis -->

## Empezar de nuevo y desinstalar

- **Documentación de un kit antiguo:** **Plan › Empezar la documentación otra vez**. **Rehacer** reabre cada unidad
  terminada para revisarla (sin borrar nada); **Borrar y empezar de cero** etiqueta `cam-docs` en git, borra lo generado
  y vuelve a empezar el plan, conservando las entrevistas, las páginas confirmadas y el tablero
  (`camaron docs reset --redo | --wipe`).
- **Desinstalar un proyecto:** **Ajustes › Kit › Desinstalar este proyecto**, primero **Ver qué borraría**. Para el portal,
  guarda `cam-docs` en un `.zip` en la carpeta temporal del sistema, quita lo que el kit añadió a cada repo y a la
  carpeta del workspace (también dentro de tu propio `.claude/` y `CLAUDE.md`), y borra `cam-docs`. Los repos quedan exactamente como en su último commit
  (`camaron uninstall`).
- **Actualizar el kit:** **Ajustes › Kit › Actualizar el kit** (`camaron self-update`) actualiza a la vez todos los proyectos
  de esta máquina y reinicia la app.

<!-- go:settings/kit -->

## Cuando algo falla

| Síntoma | Lo primero que probar |
|---|---|
| Falta una herramienta o tiene otra versión | **Calidad › Requisitos y herramientas**, o `camaron doctor` |
| Alguien editó o borró un fichero o un enlace del kit | **Ajustes › Kit › Reparar los archivos del kit**, o `camaron repair` |
| Ya tenías tu propio `.claude/` o `CLAUDE.md` en la carpeta del espacio de trabajo | Nada: setup y **Reparar** enlazan dentro de tu carpeta lo del kit e importan sus reglas en tu `CLAUDE.md`; un fichero tuyo que no se puede combinar sale como tuyo y se queda |
| Un repo privado no se clona | Guarda un token en **Ajustes › Tokens** y **Clonar o actualizar los repos** |
| Una sesión de agente dejó una unidad a medias | **Plan**, abre la unidad y **Seguir** (o **Empezar de cero**) |
| Una unidad de una ejecución queda bloqueada al fusionar | La resuelve su unidad `integrate:<unidad>`; o **Reintentar** |
| El portal no enseña un botón que esperabas | No ejecuta nada en tu máquina: hazlo en la app |

La [guía de la app](app.md#cuando-algo-falla) tiene los mensajes propios de la app.
