from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from app.llm.errors import PromptNotFoundError

_PROMPTS_DIR = Path(__file__).resolve().parent
_FRONTMATTER_DELIM = "---"


@dataclass(frozen=True)
class PromptRecord:
    name: str
    version: str
    description: str
    template: str
    path: str


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    stripped = text.lstrip()
    if not stripped.startswith(_FRONTMATTER_DELIM):
        return {}, text
    rest = stripped[len(_FRONTMATTER_DELIM) :].lstrip("\n")
    end = rest.find(f"\n{_FRONTMATTER_DELIM}")
    if end < 0:
        raise ValueError("Prompt file is missing a closing frontmatter delimiter.")
    raw_meta = rest[:end]
    body = rest[end + len(_FRONTMATTER_DELIM) + 1 :].lstrip("\n")
    meta = yaml.safe_load(raw_meta) or {}
    if not isinstance(meta, dict):
        raise ValueError("Prompt frontmatter must be a mapping.")
    return {str(key): str(value) for key, value in meta.items()}, body


def _load_manifest() -> dict[str, dict[str, str]]:
    manifest_path = _PROMPTS_DIR / "manifest.yaml"
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    prompts = payload.get("prompts", {})
    if not isinstance(prompts, dict):
        raise ValueError("Prompt manifest 'prompts' must be a mapping.")
    return prompts


@lru_cache(maxsize=1)
def load_all() -> dict[str, PromptRecord]:
    records: dict[str, PromptRecord] = {}
    for name, spec in _load_manifest().items():
        relative = spec["file"]
        version = str(spec["version"])
        path = _PROMPTS_DIR / relative
        meta, template = _parse_frontmatter(path.read_text(encoding="utf-8"))
        records[name] = PromptRecord(
            name=meta.get("name", name),
            version=meta.get("version", version),
            description=meta.get("description", ""),
            template=template,
            path=str(path),
        )
    return records


def get_prompt(name: str) -> PromptRecord:
    record = load_all().get(name)
    if record is None:
        raise PromptNotFoundError(f"Unknown prompt '{name}'.")
    return record


def list_prompts() -> list[PromptRecord]:
    return sorted(load_all().values(), key=lambda item: item.name)
