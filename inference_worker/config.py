import os
import re
import socket
import sys
import uuid
from pathlib import Path
from dotenv import load_dotenv


def _config_dir() -> Path:
    """Stable config directory that persists across binary updates."""
    if getattr(sys, "frozen", False):
        if sys.platform == "win32":
            base = Path(os.environ.get("LOCALAPPDATA", Path.home()))
        elif sys.platform == "darwin":
            base = Path.home() / "Library" / "Application Support"
        else:
            base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        d = base / "grid-inference-worker"
        d.mkdir(parents=True, exist_ok=True)
        # Migrate from old location (next to exe)
        env_new = d / ".env"
        if not env_new.exists():
            env_old = Path(sys.executable).resolve().parent / ".env"
            if env_old.exists():
                import shutil
                shutil.copy2(env_old, env_new)
        return d
    return Path.cwd()


CONFIG_DIR = _config_dir()
ENV_FILE = CONFIG_DIR / ".env"

load_dotenv(ENV_FILE)


def default_worker_name() -> str:
    """A worker name that's stable per-machine but unique across machines.

    The grid keys a worker by its name, so every node defaulting to the same
    "Text-Inference-Worker" collides — they fight over one identity and stats
    are meaningless. Derive a stable suffix from the hostname; for generic/empty
    hostnames fall back to a random id persisted in the config dir so it stays
    constant across restarts (a name that changes every boot fragments the
    worker's reputation and uptime).
    """
    host = socket.gethostname() or ""
    slug = re.sub(r"[^A-Za-z0-9]+", "-", host).strip("-")
    if slug and slug.lower() not in ("localhost", "localhost-localdomain"):
        return f"Text-Inference-Worker-{slug[:24]}"
    idfile = CONFIG_DIR / ".worker_id"
    try:
        sid = idfile.read_text().strip() if idfile.exists() else ""
        if not sid:
            sid = uuid.uuid4().hex[:8]
            idfile.write_text(sid)
    except OSError:
        sid = uuid.uuid4().hex[:8]
    return f"Text-Inference-Worker-{sid}"


class Settings:
    GRID_API_KEY = os.getenv("GRID_API_KEY", "")
    # `or` (not getenv default) so an explicitly-empty env var still gets a name.
    GRID_WORKER_NAME = os.getenv("GRID_WORKER_NAME") or default_worker_name()
    GRID_API_URL = os.getenv("GRID_API_URL", "https://api.aipowergrid.io")
    NSFW = os.getenv("GRID_NSFW", "true").lower() == "true"
    MAX_THREADS = int(os.getenv("GRID_MAX_THREADS", "1"))
    MAX_LENGTH = int(os.getenv("GRID_MAX_LENGTH", "4096"))
    MAX_CONTEXT_LENGTH = int(os.getenv("GRID_MAX_CONTEXT_LENGTH", "4096"))

    # Backend type: "ollama" (easy mode) or "openai" (advanced/custom)
    BACKEND_TYPE = os.getenv("BACKEND_TYPE", "ollama")

    # Ollama settings
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")

    # OpenAI-compatible settings (for vllm, sglang, lmdeploy, etc.)
    OPENAI_URL = os.getenv("OPENAI_URL", "http://127.0.0.1:8000/v1")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    # Minimize or disable reasoning on backends that support it (e.g. "low", "none"). Leave unset to not send.
    REASONING_EFFORT = os.getenv("REASONING_EFFORT", "").lower() or None

    # Model to serve (e.g. "llama3.2:3b" for ollama, "meta-llama/..." for openai)
    MODEL_NAME = os.getenv("MODEL_NAME", "")

    # Grid model name (what to advertise to the grid, with domain prefix)
    GRID_MODEL_NAME = os.getenv("GRID_MODEL_NAME", "")

    # Streaming mode — connect via WebSocket instead of HTTP polling
    GRID_STREAMING = os.getenv("GRID_STREAMING", "false").lower() == "true"
    GRID_STREAMING_URL = os.getenv("GRID_STREAMING_URL", "")  # Override WS URL (auto-derived from GRID_API_URL if empty)

    # P2P mode — connect via libp2p gossipsub instead of WebSocket
    P2P_ENABLED = os.getenv("P2P_ENABLED", "false").lower() == "true"
    P2P_LISTEN_PORT = int(os.getenv("P2P_LISTEN_PORT", "4001"))
    P2P_BOOTSTRAP_PEERS: list[str] = [
        p.strip()
        for p in os.getenv("P2P_BOOTSTRAP_PEERS", "").split(",")
        if p.strip()
    ]

    # Wallet address for rewards (Base chain)
    WALLET_ADDRESS = os.getenv("WALLET_ADDRESS", "")

    # Dashboard auth token (auto-generated on first run)
    DASHBOARD_TOKEN = os.getenv("DASHBOARD_TOKEN", "")

    @classmethod
    def validate(cls):
        if not cls.GRID_API_KEY:
            raise RuntimeError("GRID_API_KEY environment variable is required.")
