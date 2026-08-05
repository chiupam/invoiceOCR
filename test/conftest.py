"""Shared fixtures for parser tests.

Fixtures are SANITIZED pdfplumber TextBlocks extracted from real invoices
(see scripts/extract_fixtures.py) — names are replaced with placeholders,
tax IDs masked. Only the layout shape (bbox + labels + amounts) is kept.
The real PDFs never enter the repo.
"""
import json
import os

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE_DIR = os.path.join(REPO_ROOT, "test", "fixtures", "blocks")


def load_blocks(name: str):
    from core.extractors.base import TextBlock

    with open(os.path.join(FIXTURE_DIR, name), encoding="utf-8") as f:
        data = json.load(f)
    return [
        TextBlock(
            text=b["text"],
            bbox=tuple(b["bbox"]),
            confidence=b.get("confidence", 1.0),
            page=b.get("page", 0),
            block_id=b.get("block_id"),
        )
        for b in data
    ]


def get_parser(doc_type: str):
    from core.extractors.local.parsers import get_parser as _gp

    parser = _gp(doc_type)
    assert parser is not None, f"parser {doc_type} not registered"
    return parser


def parse_fixture(name: str, doc_type: str):
    """Load a fixture and run the parser. Returns ParsedInvoice."""
    blocks = load_blocks(name)
    parser = get_parser(doc_type)
    return parser.parse(blocks, file_path="")


@pytest.fixture
def fixture_dir():
    return FIXTURE_DIR
