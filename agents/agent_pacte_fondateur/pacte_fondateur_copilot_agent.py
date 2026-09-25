"""Agent conversationnel copilot pacte de fondateurs (service 1.1.13,
categorie 3) -- un seul agent, plusieurs tools (decision actee avec
l'utilisateur, 22/09/2026), boucle de tool-calling Groq.

ISOLATION VOLONTAIRE (meme decision que les tables, voir docstring de
agents/agent_pacte_fondateur/tables/pacte_fondateurs_conversation.py) :
config LLM (modele, temperature) et prompt systeme gardes en constantes
locales dans ce fichier, PAS ajoutes a agents/config/llm_config.yaml /
prompts.yaml -- ces fichiers sont partages et la binome les modifie
peut-etre en parallele pour son propre copilot (Groupe 3). Deviation
assumee de la convention "config centralisee" du repo, a reconcilier au
moment de la fusion.

NON VERIFIE PAR UN VRAI APPEL (a corriger au vu de la vraie reponse au
premier lancement reel, meme convention que legifrance_client.py) : le
tool-calling Groq (parametres `tools`/`tool_choice`, format de
`message.tool_calls`) suit l'API OpenAI-compatible documentee par Groq pour
les modeles qui le supportent -- jamais teste avec un appel reel depuis ce
repo. `openai/gpt-oss-120b` (deja utilise ailleurs dans ce repo pour la
structuration) est documente par Groq comme supportant le tool use agentique
-- hypothese a confirmer au premier lancement, pas un fait verifie.

Dette technique assumee : logique de retry dupliquee ici (5e occurrence du
meme patron dans ce repo -- voir legal_clause_guardrail_service.py pour le
decompte des 4 precedentes). Meme raison : factoriser toucherait des
fichiers hors perimetre de ce travail.
"""
import json
import logging
import os
import time

from groq import Groq
from sqlalchemy.orm import Session

from agents.agent_pacte_fondateur.tools import expliquer_clause_tool, expliquer_impact_variable_tool, recherche_generale_tool

_MODEL = "openai/gpt-oss-120b"
_TEMPERATURE = 0.2  # >0, contrairement au reste du repo (temperature=0 partout ailleurs) :
# c'est une reponse conversationnelle a formuler (pas une extraction/classification
# deterministe), un peu de variation dans la formulation est attendue. Le grounding
# (jamais inventer une source) est impose par le prompt systeme + les tools, pas par
# la temperature.
_MAX_TOOL_ITERATIONS = 4
_RATE_LIMIT_MAX_ATTEMPTS = 5
_RATE_LIMIT_BASE_DELAY_SECONDS = 3

_SYSTEM_PROMPT = """Tu es le copilot du pacte de fondateurs sur Wink. Tu aides un entrepreneur \
a comprendre les clauses de son pacte de fondateurs pendant qu'il le redige.

Regles strictes :
- Tu ne reponds JAMAIS a une question a portee juridique (explication de clause, impact \
d'une variable, question generale sur le pacte) sans d'abord appeler la tool appropriee. \
Tu ne dois jamais inventer une obligation legale, un article, ou un chiffre de memoire.
- Si une tool renvoie une erreur (ex: clause introuvable) ou une liste de sources vide, \
tu le dis honnetement a l'utilisateur plutot que d'improviser une reponse.
- Quand tu t'appuies sur une source (citation renvoyee par une tool), tu la cites \
explicitement dans ta reponse (ex: "selon l'art. 1843-4 du Code civil...").
- INTERDICTION ABSOLUE de citer un texte de loi, un arret, une jurisprudence, un \
guide ou toute reference externe qui n'apparait PAS textuellement dans le champ \
"sources" renvoye par une tool. Tu n'as pas connaissance d'une jurisprudence ou \
d'un guide par toi-meme -- si aucune tool ne te l'a fournie, cette reference \
n'existe pas pour toi. Un numero d'arret, une date, un guide institutionnel \
inventes de memoire sont pires qu'une absence de reponse : ne le fais jamais, \
meme pour renforcer une explication qui semble correcte par ailleurs.
- Reponses claires, concises, sans jargon juridique non explique -- l'utilisateur est \
un entrepreneur, pas un juriste.
- Si le contexte de page indique une clause affichee et que la question de l'utilisateur \
est ambigue ("cette clause", "elle", "l'article"...), suppose qu'il parle de cette clause -- \
ET utilise le code_clause EXACTEMENT tel que donne dans le contexte pour tes appels de tool. \
Ne le reformule JAMAIS, ne le devine JAMAIS a partir du titre affiche a l'utilisateur \
(le titre visible, ex: "Cessions libres", n'est PAS le code technique attendu par les tools).
- Regle generale valable pour TOUT identifiant technique (code_clause, nom_variable) : \
tu ne l'utilises que s'il apparait explicitement, textuellement, quelque part dans la \
conversation (contexte de page ou message de l'utilisateur). Si aucun identifiant technique \
n'est donne et que la question est trop vague pour l'identifier via recherche_generale, \
dis-le a l'utilisateur et demande-lui de preciser plutot que d'inventer un code plausible.
"""

TOOL_SCHEMAS = [
    expliquer_clause_tool.TOOL_SCHEMA,
    expliquer_impact_variable_tool.TOOL_SCHEMA,
    recherche_generale_tool.TOOL_SCHEMA,
]

_TOOL_FUNCTIONS = {
    "expliquer_clause": expliquer_clause_tool.expliquer_clause,
    "expliquer_impact_variable": expliquer_impact_variable_tool.expliquer_impact_variable,
    "recherche_generale": recherche_generale_tool.recherche_generale,
}


# Logger dedie (25/09/2026, ajoute pour diagnostiquer le bug "code_clause
# invente" signale par l'utilisateur) : trace chaque appel de tool avec ses
# arguments EXACTS et son resultat, dans la console du serveur (meme
# convention que les scripts debug_diagnostic_pacte.py/debug_reponses.py a
# la racine de backend/ -- observabilite manuelle, pas de dashboard). A
# desactiver (passer en DEBUG) une fois le bug de hallucination de
# code_clause confirme resolu en usage reel.
logger = logging.getLogger("pacte_fondateur_copilot")
logger.setLevel(logging.INFO)


class PacteFondateurCopilotAgentError(Exception):
    """Echec d'appel au LLM (Groq) apres retries, meme apres la boucle de tool-calling."""


def _get_client() -> Groq:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise PacteFondateurCopilotAgentError("GROQ_API_KEY manquant dans .env.")
    return Groq(api_key=api_key)


def _create_completion_with_backoff(client: Groq, **kwargs):
    """Identique a legal_clause_guardrail_service._create_completion_with_backoff --
    voir la docstring du module pour la decision de ne pas factoriser."""
    delay = _RATE_LIMIT_BASE_DELAY_SECONDS
    for attempt in range(_RATE_LIMIT_MAX_ATTEMPTS):
        try:
            return client.chat.completions.create(**kwargs)
        except Exception as exc:
            is_rate_limit = getattr(exc, "status_code", None) == 429
            if not is_rate_limit or attempt == _RATE_LIMIT_MAX_ATTEMPTS - 1:
                raise
            time.sleep(delay)
            delay += _RATE_LIMIT_BASE_DELAY_SECONDS


def _build_context_message(code_clause_contexte: str | None) -> str | None:
    if not code_clause_contexte:
        return None
    # BUG CORRIGE (25/09/2026, voir capture d'ecran utilisateur) : le
    # premier essai mentionnait le code_clause en une phrase narrative --
    # le LLM le paraphrasait/devinait au lieu de le recopier tel quel
    # (ex: code reel "cessions_libres" -> tool appelee avec
    # "cessions_libres_chapeau" ou "preambule_sans_investisseurs", des
    # codes plausibles mais inventes). Formulation ci-dessous : valeur
    # isolee entre guillemets + instruction explicite de copie verbatim,
    # pour reduire le risque de paraphrase par le modele.
    return (
        f'[Contexte de page -- code_clause EXACT (a copier tel quel, ne jamais reformuler) : '
        f'"{code_clause_contexte}"]'
    )


def gerer_message(
    db: Session,
    *,
    question: str,
    code_clause_contexte: str | None,
    historique: list[dict],
) -> dict:
    """Traite un message utilisateur, execute la boucle de tool-calling, et
    renvoie {reponse: str, sources: list[dict]}.

    `historique` : liste de messages precedents au format Groq/OpenAI
    ({"role": "user"|"assistant", "content": str}) -- deja limitee par
    l'appelant (voir pacte_fondateur_copilot_service.py), cette fonction ne
    tronque rien elle-meme.
    """
    client = _get_client()
    messages: list[dict] = [{"role": "system", "content": _SYSTEM_PROMPT}, *historique]

    contexte = _build_context_message(code_clause_contexte)
    user_content = f"{contexte}\n{question}" if contexte else question
    messages.append({"role": "user", "content": user_content})
    logger.info("[copilot pacte] question=%r code_clause_contexte=%r", question, code_clause_contexte)

    sources_collectees: list[dict] = []

    for _ in range(_MAX_TOOL_ITERATIONS):
        try:
            response = _create_completion_with_backoff(
                client,
                model=_MODEL,
                messages=messages,
                tools=TOOL_SCHEMAS,
                tool_choice="auto",
                temperature=_TEMPERATURE,
            )
        except Exception as exc:
            raise PacteFondateurCopilotAgentError(f"Echec de l'appel au LLM (Groq, copilot pacte) : {exc}") from exc

        message = response.choices[0].message
        tool_calls = getattr(message, "tool_calls", None)

        if not tool_calls:
            return {"reponse": message.content or "", "sources": sources_collectees}

        messages.append({
            "role": "assistant",
            "content": message.content,
            "tool_calls": [tc.model_dump() for tc in tool_calls],
        })

        for tool_call in tool_calls:
            nom_tool = tool_call.function.name
            fonction = _TOOL_FUNCTIONS.get(nom_tool)
            if fonction is None:
                # Le LLM a hallucine un nom de tool -- ne jamais l'executer silencieusement.
                resultat = {"erreur": f"Tool '{nom_tool}' inconnue."}
            else:
                arguments = json.loads(tool_call.function.arguments)

                # CORRECTIF (26/09/2026, point 1 demande par l'utilisateur) :
                # on ne fait plus confiance au code_clause que le LLM a choisi
                # d'envoyer. Quand le contexte de page fournit deja un
                # code_clause (l'utilisateur regarde une clause precise), on
                # ecrase la valeur de l'argument avant execution -- le LLM ne
                # decide plus jamais ce champ dans ce cas, il n'a plus qu'a
                # decider QUAND appeler la tool, pas QUEL code lui donner.
                # Remplace l'ancien mecanisme de "rattrapage" post-erreur
                # (devenu structurellement inutile ici : l'erreur qu'il
                # corrigeait ne peut plus se produire quand code_clause_contexte
                # est fourni). Le LLM reste seul responsable du code_clause
                # uniquement pour une question libre nommant une clause hors
                # contexte de page -- cas non couvert ici, laisse a
                # recherche_generale plutot qu'a un code invente.
                if code_clause_contexte and nom_tool in ("expliquer_clause", "expliquer_impact_variable"):
                    arguments["code_clause"] = code_clause_contexte

                logger.info(
                    "[copilot pacte] tool_call=%s arguments=%s (code_clause_contexte=%r)",
                    nom_tool, arguments, code_clause_contexte,
                )
                resultat = fonction(db, **arguments)
                logger.info("[copilot pacte] resultat_tool=%s", resultat)

                sources_collectees.extend(resultat.get("sources", []))

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(resultat, ensure_ascii=False),
            })

    raise PacteFondateurCopilotAgentError(
        f"Le copilot n'a pas produit de reponse finale apres {_MAX_TOOL_ITERATIONS} iterations de tool-calling."
    )
