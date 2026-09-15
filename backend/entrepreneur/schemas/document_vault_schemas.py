"""Schémas Pydantic pour la vue "coffre-fort documentaire" (service 1.1.17,
Groupe 4). Réponses enrichies combinant `documents` et `document_versions`,
pour que le frontend affiche nom de fichier/taille en un seul appel plutôt
que de rappeler `document_versions` à part.

Fichier distinct de document_schemas.py : responsabilité différente — ce
schéma est propre à la vue de consultation (1.1.17), pas au modèle brut
`documents` (0.0.2). `DocumentType` réutilisé tel quel depuis
document_schemas.py plutôt que redéfini ici, pour ne pas avoir deux sources
de vérité sur les valeurs autorisées.

Pas de champ URL de téléchargement ici : le téléchargement (version courante
ou historique) passe par les routes authentifiées de document_vault_router.py,
pas par une URL Cloudinary exposée telle quelle — voir ce fichier pour pourquoi.
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from backend.entrepreneur.schemas.document_schemas import DocumentType


class DocumentVaultItemRead(BaseModel):
    id: UUID
    document_type: DocumentType
    # Champs de la dernière version — None si le document n'a exceptionnellement
    # aucune version encore rattachée (current_version_id nullable en base).
    # Le frontend utilise `original_filename is None` comme signal "pas de
    # fichier téléchargeable" (pas de champ booléen dédié, redondant).
    original_filename: str | None
    mime_type: str | None
    size_bytes: int | None
    created_at: datetime
    # Nombre de lignes dans document_versions pour ce document — permet au
    # frontend de masquer le contrôle "Historique" quand il n'y a rien à
    # comparer (1 seule version), sans requête GET .../versions à l'avance
    # pour chaque document de la liste.
    version_count: int


class DocumentVersionRead(BaseModel):
    """Une ligne de l'historique d'un document (GET .../versions). Contrairement à
    DocumentVaultItemRead, ces champs ne sont jamais None : une version en base a
    toujours un fichier associé (contrairement à `documents.current_version_id`,
    qui peut être nul avant le premier upload).
    """

    id: UUID
    version_number: int
    original_filename: str
    mime_type: str
    size_bytes: int
    created_at: datetime
    # True si c'est la version pointée par `documents.current_version_id` — permet
    # au frontend de badger "actuelle" sans dupliquer la comparaison lui-même.
    is_current: bool
