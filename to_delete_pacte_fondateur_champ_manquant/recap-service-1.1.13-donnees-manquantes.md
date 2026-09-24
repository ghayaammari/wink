# Récap — Service 1.1.13, données projet manquantes (23/09/2026)

## Problème
Les variables `auto_*` (Préambule : capital, siège, SIREN, forme…) et l'identification des parties affichaient "(… non renseigné)" dans le pacte, y compris dans le document final.

**Cause principale trouvée** : `capital_social`, `lieu_immatriculation`, `nombre_actions`, `valeur_nominale` (migration `507ed2995d84`) existaient sur le modèle `ProjectLegalProfile` mais n'étaient exposées dans aucun schéma API → impossibles à remplir. Ajoutées à `ProjectLegalProfileBase` et `ProjectLegalProfileUpdate`.

## Décision UX (actée avec l'utilisateur)
Une seule détection déterministe (pas d'agent LLM), 3 moments :
1. **Début** — bandeau non bloquant + modal optionnel (estimation : sections dont l'applicabilité est déjà certaine).
2. **Pendant** — encadré de saisie dans le volet gauche de la section courante. Le PDF n'affiche jamais le contenu de la section en cours (modèle à 3 états) ; l'orange n'apparaît qu'après validation si l'utilisateur a laissé le champ vide.
3. **Fin** — modal au clic « Finaliser » + refus backend 422 tant qu'il reste une donnée manquante.
Pas de redirection. Les corrections écrivent dans la source de vérité via les endpoints existants (`PATCH /projects/{id}/legal-profile`, `PATCH /projects/{id}/associates/{associe_id}`), jamais dans `reponses`.

## Implémentation backend
- `services/document_renderer_base.py` : `ValeurManquante(str)` (texte "[Libellé — à compléter]" + `sources` = où corriger), helpers `manquant_profil`/`manquant_associe`/`run_valeur`/`_manquant`, tables de libellés/format par colonne. `render_clause_texte` produit un run `manquant=True`.
- `services/document_generation_service.py` : `_resoudre_variables_auto` et `_render_patron_associe_v2` renvoient des `ValeurManquante` ; `_donnees_manquantes(session, code_section=None, blocks=None)` (blocs assemblés pour les sections traitées + variables `auto_*` des sections non atteintes mais applicables) ; `lister_donnees_projet_manquantes` ; `donnees_projet_manquantes` dans `get_current_section_state` ; `DonneesProjetManquantesError` levée dans `finalize_session` avant tout upload ; helper `_a_des_investisseurs` extrait.
- `routes/document_generation_router.py` : `GET .../{document_type}/missing-data` ; 422 `{message, donnees_manquantes}` sur finalize.
- `schemas/document_generation_schemas.py` : `DonneeProjetManquanteRead {table, champ, libelle, format, associe_id, associe_nom, sections}`, champ `donnees_projet_manquantes` sur `SectionStateRead`.
- `services/pdf_rendering_service.py` : runs `manquant` en orange `#E67E22` (rouge conservé pour les valeurs renseignées).

## Limites / points ouverts
- Statuts (1.1.4) : partagent `_resoudre_variables_auto` → leurs champs profil manquants (ex. `objet_social`, `duree_societe`) deviennent aussi bloquants à la finalisation (corrigeables via le PATCH legal-profile). Les résolveurs propres aux statuts (`statuts_sas_resolvers.py`, `_render_patron_associe_statuts`) ne sont pas convertis : placeholders textuels, non détectés, non bloquants.
- Forme juridique renseignée mais absente de `valeurs_par_forme_juridique` (ex. EURL) : trou de configuration, reste un placeholder non bloquant.
- **À trancher** : SIREN / ville RCS pour une société pas encore immatriculée (`project_type='not_created'`) → aujourd'hui bloquant, impossible à remplir.
- Frontend (bandeau, encadré, modal, types TS `projectApi.ts` pour les 4 nouveaux champs) : pas encore fait.
- Vérifié : py_compile + pyflakes, test d'import du service et des résolveurs sur objets simulés. Pas testé contre la vraie base.
