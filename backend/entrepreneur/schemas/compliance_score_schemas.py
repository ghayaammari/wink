"""Schéma de réponse partagé pour les 4 endpoints de score de conformité

(RGPD, AI Act, HealthTech, FinTech) — un seul schéma, réutilisé tel quel par
chaque domaine plutôt que dupliqué 4 fois (voir compliance_score_service.py
pour le calcul)."""
from pydantic import BaseModel


class ComplianceScoreRead(BaseModel):
    # None tant qu'il n'y a aucune obligation à évaluer (pas encore de
    # diagnostic généré, ou diagnostic sans obligation applicable) — jamais
    # 0, qui laisserait croire à tort que le projet est non conforme.
    score: int | None
    total_obligations: int
    obligations_accomplies: int
