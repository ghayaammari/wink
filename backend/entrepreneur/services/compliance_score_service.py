"""Calcul du score de conformité — pourcentage d'obligations accomplies

parmi le total, pour un diagnostic donné (RGPD, AI Act, HealthTech, FinTech).
Fichier partagé entre les 4 domaines de compliance_agent : pas un fichier
par table (ce n'est pas un modèle), mais une seule responsabilité claire
(ce calcul) réutilisée pour éviter 4 copies quasi identiques.

Calcul volontairement déterministe, jamais délégué au LLM/agent — cohérent
avec la règle déjà en place que l'agent ne peut jamais se marquer lui-même
une obligation comme accomplie (voir rgpd_service.py / sync_obligations) :
seul l'entrepreneur, via un PATCH explicite, fait passer une obligation à
"fait"/"accompli", donc seul ce geste doit compter dans le score.
"""


def compute_compliance_score(obligations_accomplies: list[bool]) -> int | None:
    """Retourne le pourcentage (0-100, arrondi) d'obligations accomplies.

    Retourne `None` si la liste est vide (aucune obligation applicable ou
    diagnostic pas encore généré) — pour éviter qu'un frontend affiche à
    tort "0%" (péjoratif, alors qu'il n'y a rien à accomplir) ou "100%"
    (trompeur, alors qu'aucune obligation n'a été vérifiée).
    """
    if not obligations_accomplies:
        return None
    return round(100 * sum(obligations_accomplies) / len(obligations_accomplies))
