#!/usr/bin/env python3
"""
Consulta el saldo disponible y lo gastado de tu OpenRouter API key.

No necesita dependencias externas (solo biblioteca estandar) ni jq:
funciona igual en Windows, macOS y Linux con Python 3.7+.

Uso:
    python saldo.py
    python saldo.py --json      # volcado JSON crudo de la API

La key se lee de la variable de entorno OPENROUTER_API_KEY o, si no existe,
del fichero .env (buscado en el directorio actual y en el del script, y
subiendo por sus carpetas padre). Nunca la escribas dentro de este fichero
ni la subas a git.

Codigos de salida:
    0 = ok, queda saldo
    1 = error (falta la variable, key invalida, red, ...)
    3 = saldo agotado (limit_remaining <= 0)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

API_URL = "https://openrouter.ai/api/v1/key"
ENV_VAR = "OPENROUTER_API_KEY"
ENV_FILE = ".env"


def die(msg: str, code: int = 1):
    print(msg, file=sys.stderr)
    sys.exit(code)


def find_env_file() -> Path | None:
    """Busca .env en el directorio actual y en el del script, subiendo por los padres."""
    starts = [Path.cwd(), Path(__file__).resolve().parent]
    seen = set()
    for start in starts:
        for folder in [start, *start.parents]:
            if folder in seen:
                continue
            seen.add(folder)
            candidate = folder / ENV_FILE
            if candidate.is_file():
                return candidate
    return None


def load_env_file(path: Path) -> None:
    """Carga KEY=VALUE del .env en os.environ sin sobreescribir variables ya definidas."""
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        name, sep, value = line.partition("=")
        if not sep:
            continue
        name = name.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        os.environ.setdefault(name, value)


def get_key() -> str:
    key = os.environ.get(ENV_VAR, "").strip()
    if not key:
        env_file = find_env_file()
        if env_file is not None:
            load_env_file(env_file)
            key = os.environ.get(ENV_VAR, "").strip()
    if not key:
        die(
            f"ERROR: no encuentro {ENV_VAR} ni en las variables de entorno ni en un fichero {ENV_FILE}.\n"
            f"  Crea un {ENV_FILE} con la linea:  {ENV_VAR}=sk-or-v1-...\n"
            "  o exporta la variable:\n"
            "  Windows (PowerShell):  $env:OPENROUTER_API_KEY = \"sk-or-v1-...\"\n"
            "  macOS/Linux:           export OPENROUTER_API_KEY=sk-or-v1-...",
            1,
        )
    if key.startswith("Bearer "):
        key = key.split(" ", 1)[1].strip()
    return key


def fetch(key: str) -> dict:
    req = urllib.request.Request(API_URL, headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.load(resp).get("data", {})
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        if e.code == 401:
            die(
                "ERROR 401: la key no es valida.\n"
                "  - Revisa que la copiaste ENTERA (empieza por sk-or-v1-).\n"
                "  - Comprueba que no sobra un espacio o un salto de linea.",
                1,
            )
        die(f"ERROR HTTP {e.code}: {body}", 1)
    except urllib.error.URLError as e:
        die(f"ERROR de red: no puedo conectar con openrouter.ai ({e.reason}).\n"
            "  Comprueba tu conexion a internet / proxy / VPN.", 1)
    except Exception as e:  # pragma: no cover
        die(f"ERROR inesperado: {e}", 1)
    return {}


def money(value) -> str:
    """Formatea un importe en USD. None => 'sin limite'."""
    if value is None:
        return "sin limite"
    try:
        return f"${float(value):.2f}"
    except (TypeError, ValueError):
        return str(value)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Consulta tu saldo de OpenRouter (gastado + disponible)."
    )
    parser.add_argument("--json", action="store_true", help="salida JSON cruda de la API")
    args = parser.parse_args()

    data = fetch(get_key())

    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        remaining = data.get("limit_remaining")
        return 3 if (remaining is not None and float(remaining) <= 0) else 0

    usage = data.get("usage")
    limit = data.get("limit")
    remaining = data.get("limit_remaining")
    reset = data.get("limit_reset")

    print("OpenRouter - estado de tu key")
    print("-" * 40)
    print(f"  Key (etiqueta):   {data.get('label', 'n/d')}")
    print(f"  Gastado:          {money(usage)}")
    print(f"  Limite:           {money(limit)}")
    print(f"  DISPONIBLE:       {money(remaining)}")
    print(f"  Se renueva:       {reset if reset else 'no (limite total, sin reset)'}")
    print("-" * 40)

    if limit is None:
        print("Esta key no tiene tope propio: el gasto lo limita el credito")
        print("global de la cuenta. Cuando se agote, las peticiones fallaran.")
        return 0

    if remaining is not None and float(remaining) <= 0:
        print("SALDO AGOTADO: no te queda credito. Las peticiones daran error")
        print("hasta que se recargue (escribe a tu profesor/a).")
        return 3

    if usage is not None and limit and float(usage) / float(limit) >= 0.8:
        print("AVISO: has gastado mas del 80% de tu limite. Ve con cuidado")
        print("con las tandas largas de peticiones.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
