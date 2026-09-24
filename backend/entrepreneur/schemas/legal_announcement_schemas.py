"""Schémas Pydantic du service 1.1.5 — annonce légale de constitution."""
from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProblemeAnnonceRead(BaseModel):
    """Même format que la pré-validation des statuts : `page` = où corriger."""
    code: str
    message: str
    page: str


class LegalAnnouncementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    texte_annonce: str
    statut: str
    date_generation: datetime
    date_validation_utilisateur: datetime | None
    journal_utilise: str | None
    date_publication: date | None
    attestation_document_id: UUID | None


class LegalAnnouncementStateRead(BaseModel):
    """État complet de la page Annonce légale en un seul appel."""
    annonce: LegalAnnouncementRead | None
    pret_a_generer: bool
    problemes: list[ProblemeAnnonceRead]
    avertissements: list[ProblemeAnnonceRead]
    departement: str | None
    departement_nom: str | None


class LegalAnnouncementTextUpdate(BaseModel):
    texte_annonce: str = Field(min_length=1, max_length=10000)

    @field_validator("texte_annonce")
    @classmethod
    def _non_vide(cls, valeur: str) -> str:
        if not valeur.strip():
            raise ValueError("Le texte de l'annonce ne peut pas être vide.")
        return valeur.strip()


class JournalHabiliteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nom_journal: str
    type_support: str
    lien_site: str | None


class JournauxHabilitesRead(BaseModel):
    departement: str | None
    departement_nom: str | None
    journaux: list[JournalHabiliteRead]
    # Toujours renvoyé : filet si notre référentiel est vide ou incomplet
    # pour ce département (collecte annuelle, validation humaine).
    lien_recherche_officielle: str
