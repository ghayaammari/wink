"""Quel compte entrepreneur a deja un research_need en base (depot manuel
via l'UI, jamais fait par un script de seed -- voir docstring de
seed_startup.py : 'Ne depose AUCUN research_need')."""
from dotenv import load_dotenv

load_dotenv("backend/.env")

from backend.matching.models.research_need import ResearchNeed
from backend.entrepreneur.models.project import Project
from backend.entrepreneur.models.entrepreneur_profile import EntrepreneurProfile
from backend.shared.database import SessionLocal
from backend.shared.models.user import User

db = SessionLocal()
rows = (
    db.query(ResearchNeed, Project, User)
    .join(Project, ResearchNeed.project_id == Project.id)
    .join(EntrepreneurProfile, Project.entrepreneur_profile_id == EntrepreneurProfile.id)
    .join(User, EntrepreneurProfile.user_id == User.id)
    .all()
)

if not rows:
    print("Aucun research_need trouve en base.")
for need, project, user in rows:
    print(f"Compte : {user.email}")
    print(f"  Projet     : {project.sector or '(secteur non renseigne)'}")
    print(f"  Besoin     : [{need.type_besoin}] {need.titre}")
    print(f"  Statut     : {need.statut}")
    print()

db.close()
