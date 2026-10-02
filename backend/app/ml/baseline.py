from __future__ import annotations

import re
from dataclasses import dataclass

from app.ml.labels import IncidentLabel


@dataclass(frozen=True)
class BaselinePrediction:
    label: IncidentLabel | None
    confidence: float = 0.0
    matched: bool = False


class RuleBaseline:
    def __init__(self) -> None:
        self.es_pending = re.compile(
            r"(tardando|demorando|aun no|todavia no|no llega|esperando|no ha llegado|hace horas)",
            re.I,
        )
        self.es_declined = re.compile(r"(rechazada|rechazado|declinada|denegada|negada)", re.I)
        self.es_reversed = re.compile(r"(devuelto|devolvieron|reembolsado|revertida|anulada)", re.I)
        self.es_approved_unresolved = re.compile(
            r"(aprobada|aprobado).*?(no llega|no recibi|no tengo|no lo recibio)", re.I
        )
        self.es_ambiguous = re.compile(
            r"(no se|no estoy seguro|no me queda claro|confundido)", re.I
        )
        self.es_out_of_scope = re.compile(
            r"(tipo de cambio|cuenta nueva|tarjeta de credito|sucursal|clave|prestamo|prestamos)",
            re.I,
        )

        self.pt_pending = re.compile(
            r"(demorando|ainda nao|nao chegou|esperando|a espera|ha horas|faz horas)", re.I
        )
        self.pt_declined = re.compile(r"(recusada|rejeitado|declinada|negada)", re.I)
        self.pt_reversed = re.compile(r"(devolveram|revertida|reembolsado|anulada|de volta)", re.I)
        self.pt_approved_unresolved = re.compile(
            r"(aprovada|aprovado).*?(nao chegou|nao recebi|nao tenho|nao recebeu)", re.I
        )
        self.pt_ambiguous = re.compile(r"(nao sei|nao estou seguro|nao esta claro|confuso)", re.I)
        self.pt_out_of_scope = re.compile(
            r"(taxa de cambio|nova conta|cartao de credito|agencia|senha|emprestimo)", re.I
        )

    def predict(self, text: str, language: str | None = None) -> BaselinePrediction:
        if not text or not text.strip():
            return BaselinePrediction(label=None, confidence=0.0, matched=False)
        t = text.strip()
        lang = (language or "es").lower()
        if lang == "es":
            if self.es_approved_unresolved.search(t):
                return BaselinePrediction(
                    IncidentLabel.APPROVED_BUT_UNRESOLVED, confidence=0.85, matched=True
                )
            if self.es_declined.search(t):
                return BaselinePrediction(
                    IncidentLabel.FAILED_OR_DECLINED, confidence=0.8, matched=True
                )
            if self.es_reversed.search(t):
                return BaselinePrediction(IncidentLabel.REVERSED, confidence=0.8, matched=True)
            if self.es_pending.search(t):
                return BaselinePrediction(
                    IncidentLabel.PENDING_OR_DELAYED, confidence=0.75, matched=True
                )
            if self.es_ambiguous.search(t):
                return BaselinePrediction(
                    IncidentLabel.AMBIGUOUS_TRANSACTION, confidence=0.7, matched=True
                )
            if self.es_out_of_scope.search(t):
                return BaselinePrediction(IncidentLabel.OUT_OF_SCOPE, confidence=0.75, matched=True)
        elif lang == "pt":
            if self.pt_approved_unresolved.search(t):
                return BaselinePrediction(
                    IncidentLabel.APPROVED_BUT_UNRESOLVED, confidence=0.85, matched=True
                )
            if self.pt_declined.search(t):
                return BaselinePrediction(
                    IncidentLabel.FAILED_OR_DECLINED, confidence=0.8, matched=True
                )
            if self.pt_reversed.search(t):
                return BaselinePrediction(IncidentLabel.REVERSED, confidence=0.8, matched=True)
            if self.pt_pending.search(t):
                return BaselinePrediction(
                    IncidentLabel.PENDING_OR_DELAYED, confidence=0.75, matched=True
                )
            if self.pt_ambiguous.search(t):
                return BaselinePrediction(
                    IncidentLabel.AMBIGUOUS_TRANSACTION, confidence=0.7, matched=True
                )
            if self.pt_out_of_scope.search(t):
                return BaselinePrediction(IncidentLabel.OUT_OF_SCOPE, confidence=0.75, matched=True)
        return BaselinePrediction(label=None, confidence=0.0, matched=False)
