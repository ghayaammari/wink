"""Table `ai_act_data_profile` — service 3.3.12 (AI Act). Miroir de
`compliance_data_profile.py` (RGPD, service 3.3.1) : PAS capturé à
l'onboarding (I0), mais à la première visite de la carte "Conformité > AI
Act" — même raisonnement que le RGPD (le profil doit refléter l'usage réel,
pas une intention déclarée trop tôt).

1 ligne par projet (UniqueConstraint project_id). Champs nullable : NULL =
"pas encore répondu", distinct de False (même convention que
compliance_data_profile).

Différence avec le RGPD : `utilise_ia` est un champ "porte" (gate), pas une
question conditionnelle parmi d'autres — si un projet n'utilise aucun
système d'IA, le règlement (UE) 2024/1689 ne s'applique tout simplement pas,
il n'existe pas de "socle universel" d'obligations comme pour le RGPD (voir
rgpd_diagnostic_service.py, _THEMES_SOCLE). Ce champ permet à
ai_act_diagnostic_service.run_diagnostic() de court-circuiter tout appel LLM
quand `utilise_ia is False` — évite de consommer le quota Groq partagé pour
un projet structurellement hors périmètre (même discipline que
legal_article_heuristic_classifier_ai_act.py : ne jamais demander à un LLM
un fait qui peut être établi autrement).

Les 4 champs conditionnels ci-dessous correspondent chacun à un déclencheur
réel des catégories de risque AI Act (voir Annexe III et Titres II/IV/V du
règlement) — pas une liste arbitraire, un sous-ensemble volontairement
restreint aux cas les plus fréquents pour une startup, pour ne pas
complexifier le diagnostic au-delà du besoin actuel.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class AiActDataProfile(Base):
    __tablename__ = "ai_act_data_profile"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    # Champ porte (gate) — voir docstring module.
    utilise_ia: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # Titre II (Art. 5, pratiques interdites) / Annexe III (haut risque) —
    # identification biométrique à distance, catégorisation biométrique.
    usage_biometrie_ou_identification: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # Annexe III — emploi/recrutement, scoring de crédit, éducation/examens :
    # cas haut risque les plus probables pour une startup B2B/B2C.
    usage_scoring_emploi_credit_ou_education: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # Annexe III — infrastructures critiques, dispositifs de sécurité.
    usage_infrastructure_ou_securite_critique: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # Titre IV (Art. 50, transparence) — chatbot, contenu généré, deepfake :
    # interaction directe avec un utilisateur qui doit savoir qu'il parle à
    # une IA ou consulte un contenu généré.
    interagit_ou_genere_contenu_pour_utilisateurs: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # Titre V (Art. 51-56, gouvernance GPAI) — développement d'un modèle de
    # fondation/usage général, pas simple intégration d'une API tierce
    # (OpenAI, Groq...) : ne concerne qu'un projet qui entraîne/distribue son
    # propre modèle.
    developpe_modele_ia_usage_general: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("project_id", name="uq_ai_act_data_profile_project_id"),
    )
