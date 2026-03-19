"""Edit DNA serialisation — load / save as YAML."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from cutai.models.types import EditDNA

logger = logging.getLogger(__name__)


def save_style(style: EditDNA, path: str) -> str:
    """Save EditDNA to a YAML file.

    Args:
        style: The EditDNA to save.
        path: Destination file path (.yaml).

    Returns:
        The absolute path to the saved file.
    """
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    data = style.model_dump()
    with open(out, "w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, default_flow_style=False, allow_unicode=True, sort_keys=False)

    logger.info("Saved EditDNA '%s' to %s", style.name, out)
    return str(out.resolve())


def load_style(path: str) -> EditDNA:
    """Load EditDNA from a YAML file.

    Args:
        path: Path to a YAML file.

    Returns:
        Parsed EditDNA.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the YAML cannot be parsed as EditDNA.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Style file not found: {path}")

    with open(p, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    if not isinstance(data, dict):
        raise ValueError(f"Expected a YAML mapping in {path}, got {type(data).__name__}")

    try:
        dna = EditDNA(**data)
    except Exception as exc:
        raise ValueError(f"Failed to parse EditDNA from {path}: {exc}") from exc

    logger.info("Loaded EditDNA '%s' from %s", dna.name, p)
    return dna
