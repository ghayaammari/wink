"""Diagnostic ponctuel — a supprimer une fois la cause du 403 identifiee.
Teste consult/lawDecree sur un texte LODA connu et tres consulte (Constitution
du 4 octobre 1958), pour savoir si le 403 sur la Loi 78-17 est specifique a ce
texte ou si consult/lawDecree est bloque plus largement sur ce compte PISTE.

Usage (depuis wink/, venv active) :
  python _diag_loda.py
"""
from dotenv import load_dotenv

load_dotenv("backend/.env")

from scrapers.legifrance.legifrance_client import fetch_articles_in_text, LegifranceApiError

CONSTITUTION_1958 = "LEGITEXT000006071194"

print("Test consult/lawDecree sur la Constitution du 4 octobre 1958...")
try:
    articles = fetch_articles_in_text(CONSTITUTION_1958, fonds="LODA")
    print(f"OK — {len(articles)} article(s) recuperes.")
    if articles:
        print("Premier article :", articles[0]["article_numero"], "-", articles[0]["texte_brut"][:100])
except LegifranceApiError as exc:
    print("ECHEC :", exc)
