"""Interfaz de IA (arquitectura D-03). La IA solo interpreta texto y redacta con resultados del motor."""
from typing import Protocol

from schemas import Condition, InterpretResponse


class AIProvider(Protocol):
    def interpret(self, text: str) -> InterpretResponse: ...
    def write_up(self, conditions: list[Condition], route_summary: str) -> str: ...
