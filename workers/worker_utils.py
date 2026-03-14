"""Helpers deterministas compartilhados entre workers do JARVIS."""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Dict, List

from executive_planner.audit import traduzir_status

SENTENCE_SPLIT_PATTERN = re.compile(r"[.!?\n]+")
TOKEN_PATTERN = re.compile(r"[a-z0-9_]+")
STOPWORDS = {
    "a",
    "ao",
    "aos",
    "as",
    "com",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "e",
    "em",
    "na",
    "nas",
    "no",
    "nos",
    "o",
    "os",
    "ou",
    "para",
    "por",
    "que",
    "um",
    "uma",
}


def build_success_response(
    worker_id: str,
    task: Dict[str, Any],
    result_type: str,
    summary: str,
    details: Dict[str, Any],
    evidence: List[str],
    next_steps: List[str],
) -> Dict[str, Any]:
    """Monta a resposta estruturada padrao de um worker."""

    return {
        "worker": worker_id,
        "status": "accepted",
        "status_ptbr": traduzir_status("accepted"),
        "task_id": task.get("task_id"),
        "result_type": result_type,
        "summary": summary,
        "details": deepcopy(details),
        "evidence": [str(item) for item in evidence],
        "next_steps": [str(item) for item in next_steps],
    }


def build_domain_rejection(
    worker_id: str,
    task: Dict[str, Any],
    allowed_domains: List[str],
) -> Dict[str, Any]:
    """Retorna uma rejeicao deterministica por dominio incompatível."""

    return {
        "worker": worker_id,
        "status": "rejected",
        "status_ptbr": traduzir_status("rejected"),
        "task_id": task.get("task_id"),
        "reason": "invalid_domain",
        "reason_ptbr": "dominio_invalido_para_worker",
        "allowed_domains": list(allowed_domains),
        "received_domain": str(task.get("domain", "")),
        "evidence": [str(task.get("goal", "")), str(task.get("description", ""))],
    }


def domain_is_valid(task: Dict[str, Any], allowed_domains: List[str]) -> bool:
    domain = str(task.get("domain", "general"))
    return domain in allowed_domains


def extract_text(task: Dict[str, Any]) -> str:
    metadata = task.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}

    fragments = [
        str(task.get("goal", "")),
        str(task.get("description", "")),
        str(task.get("content", "")),
        str(metadata.get("content", "")),
        str(metadata.get("notes", "")),
        str(metadata.get("source_text", "")),
    ]
    observations = metadata.get("observations", [])
    if isinstance(observations, list):
        fragments.extend(str(item) for item in observations)
    return " ".join(fragment for fragment in fragments if fragment).strip()


def split_sentences(text: str, limit: int = 5) -> List[str]:
    sentences = [
        sentence.strip()
        for sentence in SENTENCE_SPLIT_PATTERN.split(text)
        if sentence.strip()
    ]
    return sentences[: max(limit, 0)]


def extract_topics(text: str, limit: int = 5) -> List[str]:
    tokens = TOKEN_PATTERN.findall(text.lower())
    topics: List[str] = []
    seen: set[str] = set()
    for token in tokens:
        if len(token) < 4 or token in STOPWORDS or token in seen:
            continue
        topics.append(token)
        seen.add(token)
        if len(topics) >= max(limit, 0):
            break
    return topics
