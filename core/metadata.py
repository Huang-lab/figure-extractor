"""Shared domain utilities for parsing pdffigures2 JSON metadata.

This module is framework-agnostic and can be used by both the Flask
service (app/service.py) and the CLI client (figure_extractor.py).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional


def parse_json_metadata_from_dict(
    metadata: List[Dict[str, Any]],
    *,
    processing_time: int = 0,
    filename: Optional[str] = None,
) -> Dict[str, Any]:
    """Parse in-memory pdffigures2 JSON list into a summary dict.

    This mirrors the structure previously built in app.service.parse_json_metadata,
    but operates on an already-loaded list of dicts.
    """
    if not isinstance(metadata, list):
        logging.error("parse_json_metadata_from_dict expected a list of objects")
        return {"error": "Invalid metadata structure"}

    figures = []
    tables = []

    for fig in metadata:
        if not fig.get("renderURL"):
            continue

        # Create a copy with sanitized filename for the URL
        item = fig.copy()
        item["renderURL"] = os.path.basename(item["renderURL"])

        if fig.get("figType") == "Figure":
            figures.append(item)
        elif fig.get("figType") == "Table":
            tables.append(item)

    doc_name = filename or "document"
    pages = len({fig.get("page", 0) for fig in metadata})

    return {
        "document": doc_name,
        "n_figures": len(figures),
        "n_tables": len(tables),
        "pages": pages,
        "time_in_millis": processing_time,
        "metadata_filename": f"{doc_name}.json",
        "figures": figures,
        "tables": tables,
    }


def load_and_parse_metadata_file(
    metadata_path: str,
    *,
    processing_time: int = 0,
    filename: Optional[str] = None,
) -> Dict[str, Any]:
    """Load a pdffigures2 JSON metadata file and return a summary dict.

    This is a pure helper that does not depend on Flask or subprocess.
    It is safe to use from both the web service and the CLI.
    """
    if not os.path.exists(metadata_path):
        logging.error("Metadata file not found: %s", metadata_path)
        return {"error": "Metadata file not found"}

    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        logging.error("Failed to load or parse metadata file %s: %s", metadata_path, exc)
        return {"error": "Invalid metadata file"}

    doc_name = filename or os.path.splitext(os.path.basename(metadata_path))[0]
    return parse_json_metadata_from_dict(
        metadata,
        processing_time=processing_time,
        filename=doc_name,
    )


def get_figure_metadata(figure_metadata: List[Dict[str, Any]], fig: str) -> Dict[str, Any]:
    """Given full figure metadata list and a figure path, return the matching record.

    This was originally defined in figure_extractor.py and moved here so both
    the CLI and service can share the same lookup logic.
    """
    fig_filename = os.path.basename(fig)
    logging.debug("Searching for renderURL ending with: /%s", fig_filename)

    render_url = next(
        (
            item.get("renderURL")
            for item in figure_metadata
            if "renderURL" in item
            and isinstance(item["renderURL"], str)
            and item["renderURL"].endswith(f"/{fig_filename}")
        ),
        None,
    )

    if render_url:
        logging.debug("Found renderURL for %s: %s", fig_filename, render_url)
        figure_info = next(
            (item for item in figure_metadata if item.get("renderURL") == render_url),
            {},
        )
        return figure_info

    logging.debug("No renderURL found for %s", fig_filename)
    return {}
