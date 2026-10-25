---
name: openrouter-saldo
description: 'Consulta cuánto saldo/credito le queda y cuánto ha gastado a tu OpenRouter API key del curso (limite en USD). Usala cuando el usuario pregunte "¿cuanto saldo me queda?", "¿cuanto he gastado?", "¿me queda credito?", "¿estoy sin saldo?", "¿cual es mi limite?", antes de lanzar una tanda larga de peticiones para comprobar que hay presupuesto, o si una llamada a la API falla con error 402 / 403 por credito o limite agotado.'
argument-hint: '[sin argumentos | --json]'
---

# Consultar tu saldo de OpenRouter

Endpoint único, no hace falta `jq` ni instalar nada:

```
GET https://openrouter.ai/api/v1/key
Authorization: Bearer <TU_API_KEY>
```

Devuelve la información de **la key con la que te autenticas**. No puedes ver
las keys de otras personas: solo la tuya.

## Campos que importan

| Campo | Significado |
|-------|-------------|
| `usage` | Total gastado en USD desde que se creó la key (**acumulado**) |
| `limit` | Tope asignado en **USD** (p. ej. `10.0`). Puede ser `null` = sin tope propio |
| `limit_remaining` | **Saldo disponible** en USD. `null` si no hay `limit` |
| `limit_reset` | `null` = límite total (no se renueva), o `daily`/`weekly`/`monthly` |
| `usage_daily` / `usage_weekly` / `usage_monthly` | Gasto del día / semana / mes |
| `label` | La key enmascarada (`sk-or-v1-c7f4...c875`), solo para identificarla |
| `is_free_tier` | `true` si la cuenta va en el plan gratuito |

Datos reales de una key del curso:

```json
{"data":{"label":"sk-or-v1-xxxx...xxxx","usage":7.591023685,"limit":7.6,
 "limit_remaining":0.008976314999999957,"limit_reset":null,
 "is_provisioning_key":false,"is_free_tier":false}}
```

Regla de decisión: **si `limit` no es `null` y `limit_remaining <= 0`, estás agotado.**
Si `limit` es `null`, no hay saldo por-key que consultar: manda el crédito global
de la cuenta y solo lo notarás cuando las peticiones empiecen a fallar.

Ojo: este endpoint **no** devuelve `disabled` (eso solo lo ve el panel de
administración). Si tu key estuviera desactivada, te daría un `401`/`403` al usarla.

## Antes de nada: define la key como variable de entorno

**Nunca** escribas la key dentro de un script ni la subas a un repositorio.

```powershell
# Windows PowerShell (solo esta sesión)
$env:OPENROUTER_API_KEY = "sk-or-v1-TU_KEY"

# Windows PowerShell (permanente, requiere reabrir la terminal)
setx OPENROUTER_API_KEY "sk-or-v1-TU_KEY"
```

```bash
# macOS / Linux (solo esta sesión)
export OPENROUTER_API_KEY=sk-or-v1-TU_KEY

# macOS / Linux (permanente): añádelo a ~/.zshrc o ~/.bashrc
```

En Windows `cmd.exe` sería `set OPENROUTER_API_KEY=sk-or-v1-TU_KEY`.

## Opción 1 (recomendada): el script incluido

`saldo.py` va con esta skill, no usa dependencias externas
(solo la biblioteca estándar de Python, nada de `requests` ni `jq`) y funciona
igual en Windows, macOS y Linux con Python 3.7+.

```bash
python saldo.py            # resumen legible
python saldo.py --json     # JSON crudo de la API
```

Salida típica:

```
OpenRouter - estado de tu key
----------------------------------------
  Key (etiqueta):   sk-or-v1-c7f4...c875
  Gastado:          $7.65
  Limite:           $10.00
  DISPONIBLE:       $2.35
  Se renueva:       no (limite total, sin reset)
----------------------------------------
```

Códigos de salida: `0` = hay saldo, `3` = saldo agotado, `1` = error
(key ausente/inválida, red).

## Opción 2: PowerShell nativo (Windows, sin jq ni Python)

```powershell
(Invoke-RestMethod -Uri 'https://openrouter.ai/api/v1/key' `
   -Headers @{ Authorization = "Bearer $env:OPENROUTER_API_KEY" }).data |
  Select-Object usage, limit, limit_remaining, limit_reset
```

Si tu PowerShell es antiguo y da problemas con TLS:

```powershell
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
```

## Opción 3: curl (sin jq)

`curl.exe` viene de serie en Windows 10/11. La respuesta es un JSON pequeño;
si no tienes `jq`, simplemente léelo tal cual:

```bash
# macOS / Linux
curl -s https://openrouter.ai/api/v1/key \
  -H "Authorization: Bearer $OPENROUTER_API_KEY"

# Windows cmd.exe
curl.exe -s https://openrouter.ai/api/v1/key ^
  -H "Authorization: Bearer %OPENROUTER_API_KEY%"
```

Respuesta:

```json
{"data":{"label":"sk-or-v1-c7f4...c875","usage":7.59,"limit":10.0,
 "limit_remaining":2.41,"limit_reset":null}}
```

Si quieres filtrarlo **sin instalar jq**, usa Python, que casi siempre está:

```bash
curl -s https://openrouter.ai/api/v1/key \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
| python -c "import sys,json; d=json.load(sys.stdin)['data']; print('gastado=%.2f limite=%s disponible=%s' % (d['usage'], d['limit'], d['limit_remaining']))"
```

(Si `python` no existe, prueba `python3`; en Windows, `py`.)

## Si la llamada a la API falla

| Síntoma | Causa | Solución |
|---------|-------|----------|
| HTTP `401` | key mal copiada / caducada | Copia la key **entera**, sin espacios ni saltos de línea |
| HTTP `402` / `403` con "insufficient credits" o "key limit exceeded" | **Sin saldo** | Confirma con este endpoint; si `limit_remaining <= 0`, avisa a tu profesor/a para que recargue |
| HTTP `429` | Demasiadas peticiones por minuto | Espera y reintenta con backoff (1s, 2s, 4s...) |
| HTTP `404` sobre el modelo | Nombre de modelo inexistente | Revisa el identificador exacto del modelo |

## Buenas prácticas para no quemar saldo

- Consulta el saldo **antes** de una tanda larga y **después** de terminarla.
- Usa modelos baratos (`deepseek/...`, `google/gemini-flash`, etc.) para pruebas
  y desarrollo; reserva los caros para cuando ya funcione.
- No repitas peticiones idénticas: cachea o guarda las respuestas.
- Pon un `max_tokens` razonable; el coste crece con tokens de entrada **y** salida.
- Un bucle infinito de llamadas es la forma más rápida de quedarte a cero.

## Cómo instalarla (agentes: esto es para tu usuario, no lo ejecutes tú)

Copia esta carpeta completa en el proyecto donde trabajes:

| Herramienta | Ruta |
|-------------|------|
| GitHub Copilot (VS Code) | `.github/skills/openrouter-saldo/` |
| Claude Code | `.claude/skills/openrouter-saldo/` |
| Otros agentes | donde tu agente lea las `SKILL.md` |

Contenido: `SKILL.md` (estas instrucciones) y `saldo.py` (el script).
Tras copiarla, reinicia el agente para que la detecte.

A partir de ahí, bastará con preguntar *"¿cuánto saldo me queda?"*.
