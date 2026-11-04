"""Incident Memory AI layer.

The Python services behind the recall and capture paths: the Meta Model API
client for Muse Spark, local embeddings through Ollama, postmortem drafting,
cited answers, and the read-only guardrail.
"""

from .config import Config, load_config
from .meta_client import MetaModelClient, MetaModelError
from .embeddings import Embedder, EMBEDDING_DIM
from .postmortem import PostmortemDrafter, PostmortemError
from .answer import AnswerBuilder, Citation
from .guardrails import ReadOnlyGuard, ActionRefusal

__all__ = [
    "Config",
    "load_config",
    "MetaModelClient",
    "MetaModelError",
    "Embedder",
    "EMBEDDING_DIM",
    "PostmortemDrafter",
    "PostmortemError",
    "AnswerBuilder",
    "Citation",
    "ReadOnlyGuard",
    "ActionRefusal",
]
