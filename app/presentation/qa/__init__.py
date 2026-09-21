"""Presentation QA and Automated Repair Package."""

from app.presentation.qa.visual_qa import VisualQAAgent, QAReport, QAViolation
from app.presentation.qa.repair_agent import PresentationRepairAgent

__all__ = [
    "VisualQAAgent",
    "QAReport",
    "QAViolation",
    "PresentationRepairAgent",
]
