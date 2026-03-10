"""
Carga de variables de entorno desde .env.

Importar este módulo al inicio para que los datos sensibles (OPENAI_API_KEY, etc.)
se lean desde .env y no queden en el código ni en el entorno del shell.
"""
from pathlib import Path

try:
    from dotenv import load_dotenv
    # Buscar .env en la raíz del proyecto (uno o dos niveles por encima de src/)
    for parent in [Path(__file__).resolve().parent.parent, Path.cwd()]:
        env_file = parent / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            break
    else:
        load_dotenv()  # fallback: .env en cwd
except ImportError:
    pass  # python-dotenv no instalado: usar solo variables de entorno del sistema
