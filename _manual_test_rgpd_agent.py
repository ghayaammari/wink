"""Test manuel ponctuel — PAS un fichier du projet, a supprimer une fois le
test fait (voir echange avec Claude). Verifie generate_rgpd_obligations()
seul (agents/regulatory_agent/rgpd_service.py) : appel Groq + validation du
schema de sortie, avec un profil et des chunks factices ecrits a la main
(pas de DB, pas de recherche vectorielle reelle ici).

Lancement : depuis wink/ (racine du repo), venv active :
  python _manual_test_rgpd_agent.py
"""
from dotenv import load_dotenv

load_dotenv("backend/.env")

from agents.regulatory_agent.rgpd_service import SourceChunk, generate_rgpd_obligations

profil = {
    "collecte_donnees_sensibles": False,
    "collecte_donnees_mineurs": False,
    "profilage": True,
    "partage_avec_tiers": True,
    "transfert_hors_ue": None,  # pas encore repondu -> ne doit pas etre traite comme "non"
}

chunks = [
    SourceChunk(
        source_id="test-1",
        texte=(
            "Tout organisme qui traite des donnees personnelles de maniere "
            "automatisee et systematique dans le cadre d'un profilage doit "
            "tenir un registre des traitements conformement a l'article 30 "
            "du RGPD, precisant les finalites, les categories de donnees et "
            "les destinataires."
        ),
    ),
    SourceChunk(
        source_id="test-2",
        texte=(
            "Lorsqu'un responsable de traitement partage des donnees "
            "personnelles avec un sous-traitant ou un tiers, un contrat de "
            "sous-traitance conforme a l'article 28 du RGPD doit etre signe, "
            "encadrant les obligations de securite et de confidentialite."
        ),
    ),
]

print("Appel du LLM (Groq)...")
result = generate_rgpd_obligations(profil, chunks)

print(f"\n{len(result.obligations)} obligation(s) generee(s) :\n")
for obligation in result.obligations:
    print("---")
    print("nom:", obligation.nom)
    print("description:", obligation.description)
    print("source_chunk_index:", obligation.source_chunk_index)
