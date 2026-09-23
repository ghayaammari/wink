"""Agents de matching cross-acteurs (EPIC-06 Investisseur-Startup, EPIC-07
Recherche-Startup) — un fichier par sous-domaine, chacun un agent one-shot
(LangGraph ReAct, même moteur que compliance_agent — voir
agents/shared/groq_runtime/react_agent_runner.py) avec ses propres tools,
construits côté backend/matching/services/ (agents/ ne touche jamais la DB
directement, même règle que compliance_agent — voir sa docstring de
séparation dans compliance_agent_tools_service.py).

Seul chercheur_matching_service.py existe pour l'instant (EPIC-07,
matching Recherche-Startup, service 7.7.2) ; investisseur_matching_
service.py (EPIC-06, matching Investisseur-Startup) n'a pas encore été
commencé.
"""
