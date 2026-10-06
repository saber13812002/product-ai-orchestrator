"""
agents/document_manager.py — STEP 5.4 / 5.5: the Document Manager.

This is a DETERMINISTIC (no-LLM) assembler. It takes the eight structured
TechnicalDocuments plus the final product spec and system architecture, and
writes the ten-file document bundle (5.4) under {DOCUMENTS_DIR}/{run_id}/:

    product.md, architecture.md,
    backend.md, database.md, api.md, frontend.md, ux.md,
    security.md, testing.md, devops.md

plus a TRACEABILITY.md index (5.5): every decision across all documents, each
with its source agent and reason, so any line in any document can be traced to
where and why it came from. Being deterministic keeps the bundle reproducible
and costs zero model tokens — the enrichment budget goes entirely to the 8
document authors.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .. import config
from ..schemas import TechnicalDocument


def _md_escape_cell(text: str) -> str:
    """Make a string safe to put inside a markdown table cell."""
    return (text or "").replace("|", "\\|").replace("\n", " ").strip()


def _bullets(items: list[str], numbered: bool = False) -> str:
    """Render a list of strings as a markdown bullet (or numbered) list."""
    if not items:
        return "_None listed._"
    lines = []
    for i, it in enumerate(items, start=1):
        marker = f"{i}." if numbered else "-"
        lines.append(f"{marker} {str(it).strip()}")
    return "\n".join(lines)


def _decisions_table(doc: TechnicalDocument) -> str:
    """Render the traceable decisions table (5.5): decision / source / reason."""
    if not doc.decisions:
        return "_No explicit decisions recorded._"
    rows = ["| # | Decision | Source | Reason |",
            "|---|----------|--------|--------|"]
    for i, d in enumerate(doc.decisions, start=1):
        rows.append(
            f"| {i} | {_md_escape_cell(d.decision)} | {_md_escape_cell(d.source)} "
            f"| {_md_escape_cell(d.reason)} |"
        )
    return "\n".join(rows)


def render_technical_document(doc: TechnicalDocument) -> str:
    """Render one structured TechnicalDocument to a readable markdown file."""
    parts: list[str] = [
        f"# {doc.document_type}",
        "",
        f"> {doc.summary.strip()}" if doc.summary.strip() else "> _No summary._",
        "",
        "## Key Decisions (traceable)",
        "",
        _decisions_table(doc),
        "",
        "## Architecture",
        "",
        doc.architecture.strip() or "_Not specified._",
        "",
        "## Components",
        "",
        _bullets(doc.components),
        "",
        "## Risks & Trade-offs",
        "",
        _bullets(doc.risks),
        "",
        "## Open Questions",
        "",
        _bullets(doc.open_questions),
        "",
        "## Implementation Notes",
        "",
        _bullets(doc.implementation_notes, numbered=True),
        "",
    ]
    return "\n".join(parts)


def _plain_section(title: str, body: str) -> str:
    return f"# {title}\n\n{(body or '').strip() or '_Not specified._'}\n"


class DocumentManager:
    """Collects the enrichment outputs and writes the ten-file bundle (5.4)."""

    def __init__(self, run_id: str, root: Path | None = None) -> None:
        self.run_id = run_id
        self.root = root or Path(config.DOCUMENTS_DIR)
        self.dir = self.root / run_id

    def write(
        self,
        technical_documents: list[TechnicalDocument],
        *,
        product_spec: str = "",
        system_architecture: str = "",
    ) -> Path:
        """Write the 10 files + TRACEABILITY.md. Returns the documents dir."""
        self.dir.mkdir(parents=True, exist_ok=True)

        # The 8 agent-produced documents, keyed by their md filename (5.4).
        by_file = {spec["file"]: None for spec in config.ENRICH_AGENTS}
        docs_by_type = {d.document_type: d for d in technical_documents}
        for spec in config.ENRICH_AGENTS:
            doc = docs_by_type.get(spec["doc_type"])
            if doc is None:
                # Fallback: match by agent name if the doc_type drifted.
                doc = next(
                    (d for d in technical_documents
                     if spec["agent"].replace("_", " ") in d.document_type.lower()),
                    None,
                )
            by_file[spec["file"]] = doc

        # 10 files. product.md + architecture.md come from the finalized output;
        # the other 8 from the enrichment agents.
        self._write("product.md",
                    _plain_section("Product Document", product_spec))
        self._write("architecture.md",
                    _plain_section("System Architecture Document", system_architecture))
        for filename, doc in by_file.items():
            if doc is not None:
                self._write(filename, render_technical_document(doc))
            else:
                # Never write a stub that hides a failed agent — flag it clearly.
                self._write(filename, f"_{filename}: NOT PRODUCED (agent failed)._")

        # 5.5 — the traceability index across ALL documents.
        self._write("TRACEABILITY.md", self._traceability_index(technical_documents))
        return self.dir

    def _write(self, filename: str, content: str) -> None:
        (self.dir / filename).write_text(content, encoding="utf-8")

    def _traceability_index(self, docs: list[TechnicalDocument]) -> str:
        """5.5 — one index of every decision -> source agent + reason."""
        lines = [
            "# Traceability Index",
            "",
            "Every design decision across the enrichment documents, with where it "
            "came from (source agent) and why. This is what makes each decision "
            "traceable end-to-end (STEP 5.5).",
            "",
        ]
        total = 0
        for doc in docs:
            if not doc.decisions:
                continue
            total += len(doc.decisions)
            lines.append(f"## {doc.document_type}")
            lines.append("")
            lines.append("| Decision | Source | Reason |")
            lines.append("|----------|--------|--------|")
            for d in doc.decisions:
                lines.append(
                    f"| {_md_escape_cell(d.decision)} | {_md_escape_cell(d.source)} "
                    f"| {_md_escape_cell(d.reason)} |"
                )
            lines.append("")
        header = (f"**{total} traceable decisions** across "
                  f"{len([d for d in docs if d.decisions])} documents.**\n"
                  if total else "_No traceable decisions recorded._\n")
        return "\n".join(lines) + "\n" + header
