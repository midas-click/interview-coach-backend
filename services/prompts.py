"""Prompt management: markdown files with YAML frontmatter.

Prompts live in ``prompts/*.md`` and carry frontmatter metadata::

    ---
    version: "1.0.0"
    purpose: "Evaluate interview quality across dimensions."
    variables:
      - transcript
    ---

    # System prompt body with {{ variables }} rendered via Jinja2.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from jinja2 import Environment, StrictUndefined
from pydantic import BaseModel, Field, ValidationError

from common.logging import get_logger

logger = get_logger("services.prompts")


class PromptTemplate(BaseModel):
    name: str
    version: str
    purpose: str
    variables: list[str] = Field(default_factory=list)
    body: str


class PromptNotFoundError(KeyError):
    pass


class PromptStore:
    """Loads and renders prompt templates from a directory of markdown files."""

    DEFAULT_DIRECTORY = Path(__file__).resolve().parents[1] / "prompts"

    def __init__(self, directory: Path | None = None) -> None:
        self._directory = directory or self.DEFAULT_DIRECTORY
        self._templates: dict[str, PromptTemplate] = {}
        self._env = Environment(undefined=StrictUndefined, autoescape=False)
        self._load()

    def _load(self) -> None:
        if not self._directory.is_dir():
            raise FileNotFoundError(f"prompts directory not found: {self._directory}")
        for path in sorted(self._directory.glob("*.md")):
            template = self._parse(path)
            self._templates[template.name] = template

    @staticmethod
    def _parse(path: Path) -> PromptTemplate:
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---"):
            raise ValueError(f"prompt file missing frontmatter: {path.name}")
        parts = text.split("---", 2)
        if len(parts) < 3:
            raise ValueError(f"malformed frontmatter in: {path.name}")
        meta = yaml.safe_load(parts[1]) or {}
        try:
            return PromptTemplate(
                name=path.stem,
                version=str(meta.get("version", "0.0.0")),
                purpose=str(meta.get("purpose", "")),
                variables=list(meta.get("variables", [])),
                body=parts[2].strip(),
            )
        except ValidationError as exc:
            raise ValueError(f"invalid frontmatter in {path.name}: {exc}") from exc

    def get(self, name: str) -> PromptTemplate:
        try:
            return self._templates[name]
        except KeyError as exc:
            raise PromptNotFoundError(f"unknown prompt: {name}") from exc

    def names(self) -> list[str]:
        return sorted(self._templates)

    def render(self, name: str, **variables: object) -> str:
        """Render a prompt, validating that declared variables are satisfied."""
        template = self.get(name)
        undeclared = set(variables) - set(template.variables)
        if undeclared:
            raise ValueError(
                f"prompt '{name}' received undeclared variables: {sorted(undeclared)}"
            )
        missing = set(template.variables) - set(variables)
        if missing:
            raise ValueError(f"prompt '{name}' missing variables: {sorted(missing)}")
        try:
            return self._env.from_string(template.body).render(**variables)
        except Exception as exc:
            raise ValueError(f"failed to render prompt '{name}': {exc}") from exc
