"""Build embed_text for Atlas Automated Embedding (Voyage auto-embed).

Atlas generates vectors server-side from the ``embed_text`` field when you
create a vector search index with ``type: "autoEmbed"``. No client-side
embedding model or stored ``embedding`` array is required.

See ``scripts/create_atlas_index.py`` for index setup.
"""

from __future__ import annotations


def build_embed_text(display_name: str, cuisine: str, ingredients_raw: str) -> str:
    """Concatenate fields Atlas will embed for semantic search."""
    return f"{display_name} | {cuisine} | {ingredients_raw}"
