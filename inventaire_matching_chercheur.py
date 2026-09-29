"""Inventaire (v5) -- projets liés aux 2 besoins reels, pour reconstruire le

dict `besoin` exact (voir chercheur_matching_orchestration_service.run_matching)
dans le script de test du golden set. Script jetable.
"""
from backend.shared.database import SessionLocal
from backend.matching.models.research_need import ResearchNeed
from sqlalchemy import text

db = SessionLocal()

needs = db.query(ResearchNeed).all()
for n in needs:
    r = db.execute(text(
        "select sector, description, technologies, value_proposition from projects where id = :pid"
    ), {"pid": str(n.project_id)})
    row = r.fetchone()
    print(f"\n=== Besoin {n.id} -> projet {n.project_id} ===")
    print(row)

db.close()
