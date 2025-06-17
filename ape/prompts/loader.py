from __future__ import annotations

"""Prompt loader for `.prompt.md` files.

This module provides a minimal implementation of the *Prompt Registry* MVP as
outlined in *dev_plan.md* and *prompt_dev.md*.

Features:
1. Parse markdown files that start with YAML front-matter containing
   - name: unique prompt identifier
   - description: short human friendly description
   - arguments: list with ``name`` / ``description`` / ``required`` fields
2. Convert the file into an in-memory ``PromptTemplate`` object that can be
   rendered with **Jinja2** using the declared arguments.
3. Lightweight directory loader ``load_prompts`` that discovers all
   ``*.prompt.md`` files inside the supplied path and returns a ``dict`` that
   maps ``name → PromptTemplate`` for quick lookup.
4. *No* hot-reload yet – a follow-up commit will integrate ``watchdog``.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any
import re

import yaml  # PyYAML
from jinja2 import Template

# ---------------------------------------------------------------------------
# 📑 Models
# ---------------------------------------------------------------------------


@dataclass
class PromptArgument:
    """Metadata for a single prompt argument."""

    name: str
    description: str = ""
    required: bool = True

    # The MCP SDK relies on a ``dict()`` method for serialisation. Using the
    # same API allows us to return these objects from ``list_prompts`` without
    # further transformation.
    def dict(self) -> Dict[str, Any]:  # noqa: D401 – simple method
        return {
            "name": self.name,
            "description": self.description,
            "required": self.required,
        }


@dataclass
class PromptTemplate:
    """In-memory representation of a prompt file."""

    name: str
    description: str
    arguments: List[PromptArgument]
    template_source: str
    _template: Template = field(init=False, repr=False)

    def __post_init__(self) -> None:  # noqa: D401 – lifecycle hook
        # Lazily compile the Jinja2 template when the object is created.
        self._template = Template(self.template_source, autoescape=False)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    def render(self, **kwargs: Any) -> str:
        """Render the template with the provided keyword arguments."""
        return self._template.render(**kwargs)

    # Extra sugar so these objects can be *roughly* treated like the upstream
    # ``mcp.types.Prompt`` model when serialised to JSON.
    def dict(self) -> Dict[str, Any]:  # noqa: D401 – simple method
        return {
            "name": self.name,
            "description": self.description,
            "arguments": [arg.dict() for arg in self.arguments],
        }


# ---------------------------------------------------------------------------
# 🔍 Loader helpers
# ---------------------------------------------------------------------------

# Regex that captures YAML front-matter at the start of the file.
_FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_prompt_file(path: Path) -> PromptTemplate:  # noqa: D401 – internal fn
    """Parse a single ``.prompt.md`` file and return a ``PromptTemplate``."""

    text = path.read_text(encoding="utf-8")
    match = _FRONT_MATTER_RE.match(text)
    if not match:
        raise ValueError("Missing YAML front-matter")

    front_matter = match.group(1)
    body = text[match.end() :]

    meta = yaml.safe_load(front_matter) or {}

    name = meta.get("name") or path.stem
    description = meta.get("description", "")

    args_meta = meta.get("arguments", [])
    arguments: List[PromptArgument] = []
    for arg in args_meta:
        arguments.append(
            PromptArgument(
                name=arg.get("name"),
                description=arg.get("description", ""),
                required=bool(arg.get("required", True)),
            )
        )

    return PromptTemplate(
        name=name,
        description=description,
        arguments=arguments,
        template_source=body,
    )


# ---------------------------------------------------------------------------
# 🛠️  Public API
# ---------------------------------------------------------------------------


def load_prompts(directory: str | Path) -> Dict[str, PromptTemplate]:
    """Load all ``*.prompt.md`` files from *directory*.

    Returns a dict mapping **prompt name → PromptTemplate**.
    """

    dir_path = Path(directory)
    if not dir_path.exists():
        raise FileNotFoundError(f"Prompt directory '{dir_path}' does not exist.")

    prompts: Dict[str, PromptTemplate] = {}
    for file_path in dir_path.glob("*.prompt.md"):
        try:
            tmpl = _parse_prompt_file(file_path)
            prompts[tmpl.name] = tmpl
        except Exception as exc:
            # Fail-soft: Log and continue.  Real code would use *loguru* but we
            # avoid the import here to keep this module dependency-free.
            print(f"⚠️  Skipping prompt file '{file_path}': {exc}")

    return prompts 