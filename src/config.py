"""
Load environment variables from .env.

Import this module at startup so sensitive data (OPENAI_API_KEY, etc.)
is read from .env and does not remain in code or shell environment.
"""
from pathlib import Path

try:
    from dotenv import load_dotenv
    # Look for .env at project root (one or two levels above src/)
    for parent in [Path(__file__).resolve().parent.parent, Path.cwd()]:
        env_file = parent / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            break
    else:
        load_dotenv()  # fallback: .env in cwd
except ImportError:
    pass  # python-dotenv not installed: use system env vars only
