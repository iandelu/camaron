"""Docs model: workspace, repo sync, incremental state, trust (draft/confirmed), translations, llms.txt, search."""
from __future__ import annotations

import math, os, re
from collections import Counter
from pathlib import Path

from .app import services
from .core.clock import now
from .domain.docs import directives, frontmatter, logical_paths, page_outline, synonyms, trust_levels
from .core.paths import cli_cmd
from .common import KIT, ROOT, DOCS, CAM_DIR, repo_dir, rel_file, save_json


# ---------- workspace ----------


# ---------- incremental state ----------


# ---------- docs model ----------


# ---------- search (portal + MCP): BM25 over body tokens, prefix-matched (pedido → pedidos) ----------


# ---------- human review ----------


