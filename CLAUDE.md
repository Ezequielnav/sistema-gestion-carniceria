# CLAUDE.md - Instrucciones para Claude Code

Proyecto: sistema de gestión para Carnicería Rojano (Trabajo de Campo, proyecto individual).
Fuente de verdad del diseño: carpeta `/docs`. Si algo contradice a `/docs`, avisar antes de seguir.

## Stack
Python + Django, PostgreSQL, Tailwind CSS + HTML + JavaScript, arquitectura por capas
(vistas / servicios / acceso a datos). Ver `docs/06-arquitectura.md`.

## Reglas de trabajo
- Trabajar siempre en una rama; nunca commitear directo a `main` (está protegida, se entra por PR).
- Cada regla RN-xx / RI-xx lleva al menos una prueba automática.
- Todo cambio de código actualiza los archivos afectados de `/docs`.
- No inventar reglas del negocio: si falta un dato, anotarlo como pregunta pendiente (PR-xx / PA-xx).
- Dinero con `DecimalField`; nunca `float`.

## Commits, Pull Requests y textos
- Nunca agregar líneas de atribución a la IA: ni `Co-Authored-By`, ni "Generated with Claude Code", ni enlaces a sesiones de Claude, en commits, Pull Requests, comentarios ni documentos.
- Nunca dejar mensajes generados por la IA que no sean parte del trabajo: firmas, emojis decorativos, frases como "como modelo de IA" o "espero que esto ayude", notas dirigidas al agente o restos de instrucciones.
- Commits y Pull Requests en español, sobrios: qué cambió y por qué, citando los IDs que correspondan (RF-xx, CU-xx, DEC-xx). Formato del título: `tipo: descripción` (por ejemplo `docs: ...`, `feat: ...`, `fix: ...`).
- Antes de commitear o abrir un PR, revisar el mensaje y quitar cualquier texto de este tipo.

## Credenciales y datos (D-14)
- Nunca leer, imprimir, copiar ni commitear `.env`, `.env.*` (salvo `.env.example`), claves ni archivos en `~/.ssh`.
- Las pruebas usan una base local de prueba con datos ficticios y credenciales exclusivas de desarrollo.
  Django lee el `.env` por su cuenta; el agente no necesita ver su contenido.
- No usar datos reales del negocio (carpeta `datos-reales/` fuera del repo).
- Si una tarea requiere un secreto real, detenerse y avisar.

## Pruebas
Correr `pytest` antes de proponer un cambio. Las pruebas no deben tocar la base de desarrollo.

## Permisos
Los permisos de lectura sobre secretos están en `.claude/settings.json`. Esas reglas no cubren procesos hijos (por ejemplo, un script que lea `.env`); no ejecutar comandos que impriman variables de entorno.

<!-- Cuando se sume Codex: mover el contenido a AGENTS.md y dejar en este archivo solo '@AGENTS.md'. -->

## Herramientas de IA (plugins del proyecto)
Karpathy guidelines y Agent Skills son de uso personal (plugins de terceros): se configuran en `.claude/settings.local.json`, que no se sube al repositorio. `.claude/settings.json` solo activa frontend-design y security-guidance.
- Karpathy guidelines: siempre activas (pensar antes, cambios mínimos y quirúrgicos).
- Agent Skills: usar /spec antes de implementar cada CU, /plan para dividirlo en tareas y /review antes de abrir un Pull Request.
- frontend-design: al crear pantallas, respetar los prototipos de /docs y Figma; no inventar un diseño nuevo.
- Playwright (MCP): probar flujos solo contra el entorno local (localhost) con datos de ejemplo.
