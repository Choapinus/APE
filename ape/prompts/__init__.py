"""APE Prompt Registry package.

This package exposes a *very small* API surface so the rest of the codebase can
interact with prompts without being coupled to any particular loader or file
format.  It intentionally mirrors the API outlined in *prompt_dev.md*.
"""

from pathlib import Path
from typing import Dict, List, Optional, Any
import os
from importlib.metadata import entry_points  # NEW

from .loader import load_prompts, PromptTemplate

# ---------------------------------------------------------------------------
# 📦 Registry initialisation (eager, but cheap)
# ---------------------------------------------------------------------------

_PROMPTS_PATH = Path(__file__).parent / "templates"  # markdown files live in subdir
_prompt_cache: Dict[str, PromptTemplate] = load_prompts(_PROMPTS_PATH)


# ---------------------------------------------------------------------------
# 🔄  Hot-reload (optional)
# ---------------------------------------------------------------------------

_observer = None  # type: ignore[var-annotated]

def _start_watchdog(path: Path) -> None:  # noqa: D401 – internal helper
    """Start watchdog observer that reloads prompts on any file change."""

    global _observer
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler

        class _ReloadHandler(FileSystemEventHandler):
            def on_modified(self, event):  # noqa: D401 – watchdog callback
                if event.is_directory:
                    return
                if not event.src_path.endswith(".prompt.md"):
                    return
                refresh()
                try:
                    from loguru import logger

                    logger.debug(
                        "🔄 [PromptRegistry] Reloaded prompts due to change in {}", event.src_path
                    )
                except Exception:
                    print(
                        "🔄 [PromptRegistry] Reloaded prompts due to change in", event.src_path
                    )

        observer = Observer()
        observer.schedule(_ReloadHandler(), str(path), recursive=False)
        observer.daemon = True
        observer.start()
        _observer = observer
    except Exception as exc:
        # Fail-soft: missing watchdog or OS limits – log & continue.
        print(f"⚠️  [PromptRegistry] Hot-reload disabled: {exc}")

# Automatically enable hot-reload when the module is imported in dev env
if os.environ.get("APE_DISABLE_PROMPT_WATCH") != "1":
    import os

    _start_watchdog(_PROMPTS_PATH)

# ---------------------------------------------------------------------------
# 🔌  Plugin integration (entry-points)
# ---------------------------------------------------------------------------

def register_prompt_directory(path: str | Path) -> None:  # noqa: D401 – public helper
    """Load all ``*.prompt.md`` files from *path* and merge into registry."""

    try:
        new_prompts = load_prompts(Path(path))
        _prompt_cache.update(new_prompts)
    except Exception as exc:
        print(f"⚠️  [PromptRegistry] Could not load plugin prompt dir '{path}': {exc}")

# Discover entry-point directories once at import time
for ep in entry_points(group="ape_prompts.dirs"):
    try:
        dir_path = ep.load()  # The object returned should be a str | Path
        register_prompt_directory(dir_path)
    except Exception as exc:  # pragma: no cover – best-effort
        print(f"⚠️  [PromptRegistry] Failed to load prompt plugin '{ep.name}': {exc}")

# ---------------------------------------------------------------------------
# 🔎 Public helpers
# ---------------------------------------------------------------------------

def list_prompts() -> List[PromptTemplate]:  # noqa: D401 – simple helper
    """Return all loaded prompts as a list."""
    return list(_prompt_cache.values())


def get_prompt(name: str) -> PromptTemplate:
    """Return *PromptTemplate* by *name*.

    Raises ``KeyError`` if the prompt does not exist.
    """
    return _prompt_cache[name]


def render_prompt(name: str, arguments: Optional[Dict[str, Any]] = None) -> str:
    """Render a prompt by *name* with the supplied *arguments*.

    Example::
        text = render_prompt("system", {"agent_name": "APE"})
    """
    tmpl = get_prompt(name)
    return tmpl.render(**(arguments or {}))


def refresh() -> None:  # noqa: D401 – simple helper
    """Reload prompt files from disk.

    *Watchdog*-based hot-reload will come in a future patch – for now this is a
    manual call that repopulates the in-memory cache.
    """
    global _prompt_cache
    _prompt_cache = load_prompts(_PROMPTS_PATH) 