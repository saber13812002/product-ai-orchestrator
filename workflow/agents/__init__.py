"""Agents for the Multi-Model Product Orchestrator.

STEP 2 defined Manager (coordinator) and ProductAnalyst (STEP 1).
STEP 5 adds the eight Design-Enrichment agents (EnrichmentAgent, one instance
per role) and the deterministic Document Manager (5.4/5.5).
"""
from .manager import Manager
from .product_analyst import ProductAnalyst
from .enrichment import EnrichmentAgent, build_enrichment_agents
from .document_manager import DocumentManager

__all__ = [
    "Manager",
    "ProductAnalyst",
    "EnrichmentAgent",
    "build_enrichment_agents",
    "DocumentManager",
]
