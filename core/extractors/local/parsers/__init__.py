"""Layout parsers: text+bbox blocks → structured ParsedInvoice.

Each Parser knows the layout of one 票据 type (medical, vat, train).
Given a list of TextBlock from any text-based backend, it finds the
field labels and extracts structured values.

The Parser registry mirrors the DocType registry in core/doc_types/:
get_parser(doc_type_id) returns the right parser for the doc type.
"""
from .base import Parser, register_parser, get_parser, all_parsers  # noqa: F401
from . import medical  # noqa: F401  -- registers "medical" parser
from . import vat  # noqa: F401  -- registers "vat" parser
