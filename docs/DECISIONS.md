# Journal des décisions techniques — Wink

*Fichier créé le 25/09/2026 (référencé par `Wink_context_project.md` mais absent du dépôt). Une entrée par décision : contexte, décision, raison, conséquences.*

---

## 2026-09-25 — Service 1.1.5 : pas de transmission automatique de l'annonce légale

**Contexte.** Le cahier des charges nomme le service « Génération et **transmission** automatisées de l'annonce légale », avec suivi jusqu'à l'attestation de parution.

**Constat.**
- La publication d'une annonce de constitution est **payante** : forfait fixé chaque année par arrêté, identique chez tous les journaux et SPEL habilités (199 € HT pour une SAS en métropole en 2026, source Service-Public F35957). Il n'existe aucune voie gratuite.
- Pappers Services (intermédiaire retenu dans la conception Groupe 5) **rédige lui-même** l'annonce depuis son formulaire. L'API n'est pas vérifiable sans compte, aucun bac à sable n'est annoncé, et chaque test réel coûte le forfait sans pouvoir être annulé.

**Décision.** v1 = Wink **rédige** l'annonce (modèle fixe, sans LLM, mentions de l'art. R210-4), la fait **valider** par l'entrepreneur, **liste les journaux habilités** du département du siège, puis enregistre l'**attestation déposée** par l'entrepreneur. La transmission et la récupération automatiques de l'attestation sont retirées du périmètre.

**Conséquences.**
- Table `legal_announcements` (remplace `legal_announcement_transmissions`, sans colonnes de transmission, d'erreur ni de tentative).
- Référentiel `jal_reference` alimenté par le registre national actulegales.fr (vers lequel renvoie Service-Public, fiche R44934), et non par les ~100 arrêtés préfectoraux.
- À reconsidérer si un partenariat JAL avec API et facturation au client final devient possible.

## 2026-09-25 — Module de formatage partagé `backend/shared/utils/`

**Décision (utilisateur).** `formater_montant`, `formater_siege_social` (ex-`_formater_siege_social`) et `formater_date` sont regroupées dans `backend/shared/utils/formatting.py`, utilisées par les statuts (1.1.4) et l'annonce légale (1.1.5). Les anciens noms restent importables depuis leurs modules d'origine (réexport). Le référentiel des départements (`departements.py`) est placé au même endroit.
