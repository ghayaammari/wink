"""Requetes Judilibre a executer pour le service 1.1.13, categorie 3 (agent
conversationnel pacte de fondateurs) -- pure donnee, meme separation que
`articles_cites_pacte_fondateurs.py`.

Perimetre volontairement RESTREINT (decision du 25/09/2026, voir echange
avec l'utilisateur) : seules les clauses les plus frequemment contestees en
pratique -- pas de couverture exhaustive des 61 clauses du pacte. Etendre
cette liste plus tard, au vu des vraies questions posees a l'agent une fois
en usage, plutot que de tout collecter par anticipation sans usage reel pour
verifier la pertinence (meme logique que la priorisation actee avec
l'utilisateur : "sans usage reel, on ne sait pas quelles clauses generent
vraiment des questions").

`taille` = nombre de decisions les plus pertinentes recuperees par requete
(pas tout le corpus Judilibre pour ce sujet) -- volume delibere reduit tant
que la relecture humaine (Phase 1.5, meme dashboard que forme_juridique)
n'a pas ete testee sur ce volume.

BUG REEL corrige le 25/09/2026 (constate sur un vrai run, 400 Bad Request) :
le code de la chambre commerciale est "comm", PAS "com" -- corrige ici (les
3 requetes ci-dessous visaient toutes cette chambre).
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class RequeteJudilibre:
    query: str
    sous_theme: str
    cite_par_code_clause: list[str]
    taille: int = 3
    chamber: str | None = None


REQUETES_PACTE_FONDATEURS: list[RequeteJudilibre] = [
    RequeteJudilibre(
        query="clause de non-concurrence associé durée contrepartie financière",
        sous_theme="non_concurrence_validite",
        cite_par_code_clause=["non_concurrence"],
        chamber="comm",
    ),
    RequeteJudilibre(
        query="clause léonine article 1844-1 pacte associés",
        sous_theme="clause_leonine",
        cite_par_code_clause=[
            "sortie_conjointe_totale_drag_along",
            "clause_ratchet",
            "non_dilution_investisseurs",
        ],
        chamber="comm",
    ),
    RequeteJudilibre(
        query="clause de préemption cession actions pacte associés violation",
        sous_theme="preemption_sanction",
        cite_par_code_clause=["cessions_libres_chapeau"],
        chamber="comm",
    ),
]
