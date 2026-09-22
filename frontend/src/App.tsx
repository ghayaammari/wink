import { useEffect, useState } from "react"
import { Navigate, Route, Routes } from "react-router-dom"
import LegalTextsValidationPage from "./admin/pages/LegalTextsValidationPage"
import SectorInsuranceValidationPage from "./admin/pages/SectorInsuranceValidationPage"
import { getMyResearcherProfile, type ResearcherProfileRead } from "./chercheur/api/researcherProfileApi"
import ResearcherOnboardingPage from "./chercheur/pages/ResearcherOnboardingPage"
import ResearcherProfileDetailsPage from "./chercheur/pages/ResearcherProfileDetailsPage"
import ResearchWorksPage from "./chercheur/pages/ResearchWorksPage"
import PastExpertisesPage from "./chercheur/pages/PastExpertisesPage"
import OnboardingWizard from "./entrepreneur/components/OnboardingWizard"
import { OnboardingWizardProvider } from "./entrepreneur/context/OnboardingWizardContext"
import DocumentVaultPage from "./entrepreneur/pages/DocumentVaultPage"
import MyProjectLayout from "./entrepreneur/pages/MyProjectLayout"
import MyProjectPage from "./entrepreneur/pages/MyProjectPage"
import PacteFondateursV2Page from "./entrepreneur/pages/PacteFondateursV2Page"
import PlanActionPage from "./entrepreneur/pages/PlanActionPage"
import ProjectGeneralInfoPage from "./entrepreneur/pages/ProjectGeneralInfoPage"
import ProjectLegalInfoPage from "./entrepreneur/pages/ProjectLegalInfoPage"
import ProjectPublicProfilePage from "./entrepreneur/pages/ProjectPublicProfilePage"
import TeamCapitalPage from "./entrepreneur/pages/TeamCapitalPage"
import { getMyInvestorProfile, type InvestorProfileRead } from "./investisseur/api/investorProfileApi"
import InvestorOnboardingPage from "./investisseur/pages/InvestorOnboardingPage"
import InvestorProfilePage from "./investisseur/pages/InvestorProfilePage"
import { getCurrentUser, type Role } from "./shared/api/authApi"
import DashboardLayout from "./shared/components/DashboardLayout"
import type { SidebarNavItem } from "./shared/components/Sidebar"
import { useAuth } from "./shared/context/AuthContext"
import ForgotPasswordPage from "./shared/pages/ForgotPasswordPage"
import LoginPage from "./shared/pages/LoginPage"
import ProfilePage from "./shared/pages/ProfilePage"
import ResetPasswordPage from "./shared/pages/ResetPasswordPage"
import SignupPage from "./shared/pages/SignupPage"

const ICON_PROJECT = (
  <path
    strokeLinecap="round"
    strokeLinejoin="round"
    d="M2.25 12.75V12A2.25 2.25 0 0 1 4.5 9.75h15A2.25 2.25 0 0 1 21.75 12v.75m-19.5 0v6a2.25 2.25 0 0 0 2.25 2.25h15a2.25 2.25 0 0 0 2.25-2.25v-6m-19.5 0-.001-2.25A2.25 2.25 0 0 1 4.5 8.25h4.086a2.25 2.25 0 0 1 1.591.659l1.828 1.828a.75.75 0 0 0 .53.22h4.965A2.25 2.25 0 0 1 19.75 12.75"
  />
)

// Icône "document" — nav "Mes travaux" côté chercheur (voir CHERCHEUR_NAV_ITEMS).
const ICON_DOCUMENT = (
  <path
    strokeLinecap="round"
    strokeLinejoin="round"
    d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m3.75 9v6m3-3H9m1.5-12H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z"
  />
)

// Icône "mallette" — nav "Mes expertises" côté chercheur (voir CHERCHEUR_NAV_ITEMS).
const ICON_BRIEFCASE = (
  <path
    strokeLinecap="round"
    strokeLinejoin="round"
    d="M20.25 14.15v4.25c0 1.094-.787 2.036-1.872 2.18-2.087.277-4.216.42-6.378.42s-4.291-.143-6.378-.42c-1.085-.144-1.872-1.086-1.872-2.18v-4.25m16.5 0a2.18 2.18 0 0 0 .75-1.661V8.706c0-1.081-.768-2.015-1.837-2.175a48.114 48.114 0 0 0-3.413-.387m4.5 8.006c-.194.165-.42.295-.673.38A23.978 23.978 0 0 1 12 15.75c-2.648 0-5.195-.429-7.577-1.22a2.016 2.016 0 0 1-.673-.38m0 0A2.18 2.18 0 0 1 3 12.489V8.706c0-1.081.768-2.015 1.837-2.175a48.111 48.111 0 0 1 3.413-.387m7.5 0V5.25A2.25 2.25 0 0 0 13.5 3h-3a2.25 2.25 0 0 0-2.25 2.25v.894m7.5 0a48.667 48.667 0 0 0-7.5 0"
  />
)

// Icône "liste à cocher" — nav "Plan d'action" côté entrepreneur (voir
// ENTREPRENEUR_NAV_ITEMS). Distincte de ICON_PROJECT (dossier) : la roadmap
// est une checklist d'étapes, pas un ensemble de sections à éditer.
const ICON_CHECKLIST = (
  <path
    strokeLinecap="round"
    strokeLinejoin="round"
    d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"
  />
)

// Navigation métier de l'entrepreneur — "Mon projet" se déplie en 5
// sous-sections (voir Sidebar.tsx : dépliage automatique selon l'URL, pas de
// bouton toggle séparé). "Plan d'action" (roadmap pré-création, service
// formalisé dans "Wink — Plan d'action pré-création : spécification") est une
// entrée de premier niveau distincte, pas une sous-section de "Mon projet" —
// son contenu (24 nœuds EPIC-01) est différent des 5 profils du projet.
// L'affichage conditionnel à project_type === "not_created" est géré DANS
// PlanActionPage, pas ici : la nav reste statique par rôle dans ce fichier,
// pas par état de projet (voir Sidebar.tsx, aucune autre entrée ne dépend
// d'un état métier). "Mon profil" et la déconnexion sont gérés par Sidebar
// elle-même, pas listés ici.
const ENTREPRENEUR_NAV_ITEMS: SidebarNavItem[] = [
  {
    to: "/entrepreneur/mon-projet",
    label: "Mon projet",
    icon: ICON_PROJECT,
    children: [
      { to: "/entrepreneur/mon-projet/informations-generales", label: "Informations générales" },
      { to: "/entrepreneur/mon-projet/informations-legales", label: "Informations légales" },
      { to: "/entrepreneur/mon-projet/equipe-capital", label: "Équipe & capital" },
      { to: "/entrepreneur/mon-projet/vitrine-publique", label: "Vitrine publique" },
      { to: "/entrepreneur/mon-projet/coffre-fort", label: "Coffre-fort documentaire" },
      // NETTOYAGE v1 (26/09/2026) : le lien vers "pacte-fondateurs" (v1) a ete retire, page supprimee.
      // Route/label encore "-v2" volontairement -- renommer l'URL est une decision UX distincte
      // (impact bookmarks/liens existants), pas faite ici sans validation explicite.
      { to: "/entrepreneur/mon-projet/pacte-fondateurs-v2", label: "Pacte de fondateurs" },
    ],
  },
  { to: "/entrepreneur/plan-action", label: "Plan d'action", icon: ICON_CHECKLIST },
]

// Navigation métier du chercheur — "Mes travaux" (service 0.0.2/0.0.3 :
// dépôt manuel + consultation, voir ResearchWorksPage) et "Mes expertises"
// (service optionnel, page à part entière — voir PastExpertisesPage) : deux
// entrées distinctes de la nav, pas une sous-section l'une de l'autre.
// Le profil de recherche (ORCID, affiliation, résumés) est fusionné avec
// "Mon profil" (profileTo="/chercheur/profile", géré par DashboardLayout /
// Sidebar), plus d'entrée séparée ici.
const CHERCHEUR_NAV_ITEMS: SidebarNavItem[] = [
  { to: "/chercheur/travaux", label: "Mes travaux", icon: ICON_DOCUMENT },
  { to: "/chercheur/expertises", label: "Mes expertises", icon: ICON_BRIEFCASE },
]

// Investisseur : parcours linéaire (thèse, email de contact, organisation),
// pas de page métier séparée type "Mes travaux" — tout tient dans le profil
// (voir InvestorProfilePage, accessible via profileTo="/investisseur/profile"),
// donc pas d'item de nav métier supplémentaire pour l'instant.
const EMPTY_NAV_ITEMS: SidebarNavItem[] = []

type PostLoginDestination = "loading" | "auth_error" | Role

/** Routing post-login : décide, une seule fois après connexion, vers quel
 * espace rediriger — dépend uniquement du rôle. Ne rend jamais de contenu
 * lui-même : uniquement des redirections, pour que l'URL affichée reflète
 * toujours l'espace réellement actif ("/entrepreneur/...", pas juste "/").
 *
 * Pour l'entrepreneur, ne vérifie PAS l'existence d'un projet (ancien
 * comportement : un GET /projects/me ici, en plus de celui refait juste après
 * par MyProjectLayout — double fetch à chaque connexion). Cette vérification
 * est déjà faite par MyProjectLayout, seul endroit qui en a besoin — voir ce
 * fichier pour la redirection vers /onboarding si `project === null`. Même
 * principe pour le chercheur : voir ChercheurDashboardRoute ci-dessous. */
function HomeRoute() {
  const { accessToken, isAuthenticated } = useAuth()
  const [destination, setDestination] = useState<PostLoginDestination>("loading")

  useEffect(() => {
    if (!isAuthenticated || !accessToken) return

    getCurrentUser(accessToken)
      .then((user) => setDestination(user.role))
      // Échec de GET /auth/me (ex: access token expiré) : on ne devine pas de
      // rôle, on renvoie vers /login plutôt que vers un espace dashboard au
      // hasard — remplace l'ancien fallback générique "home" de HomePage
      // (supprimée, voir DashboardLayout).
      .catch(() => setDestination("auth_error"))
    // eslint-disable-next-line react-hooks/exhaustive-deps -- ne doit tourner qu'au montage
  }, [isAuthenticated, accessToken])

  if (!isAuthenticated) {
    return <Navigate to="/signup" replace />
  }
  if (destination === "loading") {
    return <p className="p-8 text-center text-sm text-gray-500">Chargement...</p>
  }
  if (destination === "auth_error") {
    return <Navigate to="/login" replace />
  }
  return <Navigate to={`/${destination}`} replace />
}

function OnboardingRoute() {
  const { isAuthenticated } = useAuth()
  if (!isAuthenticated) {
    return <Navigate to="/signup" replace />
  }
  return (
    <OnboardingWizardProvider>
      <OnboardingWizard />
    </OnboardingWizardProvider>
  )
}

/** Garde d'accès pour /admin/legal-texts — vérifie juste l'authentification,
 * comme OnboardingRoute : pas de rôle "admin" dans le système actuel (users
 * n'a que entrepreneur/chercheur/investisseur), donc n'importe quel compte
 * connecté peut y accéder pour l'instant. Même dette technique assumée que
 * côté backend (voir legal_texts_validation_router.py) — à resserrer si ce
 * dashboard devient accessible à autre chose qu'un usage interne/dev. */
function AdminRoute() {
  const { isAuthenticated } = useAuth()
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }
  return <LegalTextsValidationPage />
}

function AdminSectorInsuranceRoute() {
  const { isAuthenticated } = useAuth()
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }
  return <SectorInsuranceValidationPage />
}

/** Garde d'accès pour /chercheur/onboarding — même pattern que OnboardingRoute
 * ci-dessus (vérifie juste l'authentification, pas la complétion : on est
 * justement en train de la compléter ici). */
function ChercheurOnboardingRoute() {
  const { isAuthenticated } = useAuth()
  if (!isAuthenticated) {
    return <Navigate to="/signup" replace />
  }
  return <ResearcherOnboardingPage />
}

/** Même pattern côté investisseur — voir ChercheurOnboardingRoute. */
function InvestisseurOnboardingRoute() {
  const { isAuthenticated } = useAuth()
  if (!isAuthenticated) {
    return <Navigate to="/signup" replace />
  }
  return <InvestorOnboardingPage />
}

/** Template de base du dashboard, instancié une fois par acteur (voir
 * ChercheurDashboardRoute/InvestisseurDashboardRoute ci-dessous) — seule la
 * navigation métier passée à DashboardLayout change d'un acteur à l'autre. */
function EntrepreneurDashboardRoute() {
  const { isAuthenticated } = useAuth()
  if (!isAuthenticated) {
    return <Navigate to="/signup" replace />
  }
  return (
    <DashboardLayout
      roleLabel="Entrepreneur"
      navItems={ENTREPRENEUR_NAV_ITEMS}
      profileTo="/entrepreneur/profile"
    />
  )
}

type ChercheurGateState = "loading" | "incomplete" | ResearcherProfileRead

/** Porte d'entrée du dashboard chercheur — fetch le profil une seule fois
 * (comme MyProjectLayout côté entrepreneur) et redirige vers l'onboarding
 * tant que profile_completion !== "complet". Une fois complet, affiche le
 * dashboard normal avec la navigation métier "Mes travaux". */
function ChercheurDashboardRoute() {
  const { isAuthenticated, accessToken } = useAuth()
  const [state, setState] = useState<ChercheurGateState>("loading")

  useEffect(() => {
    if (!isAuthenticated || !accessToken) return

    getMyResearcherProfile(accessToken)
      .then((profile) => setState(profile.profile_completion === "complet" ? profile : "incomplete"))
      // Erreur réseau/serveur : on ne bloque pas l'utilisateur indéfiniment sur
      // "Chargement..." — on le renvoie compléter l'onboarding, quitte à ce que
      // GET /chercheur/profile échoue à nouveau et redonne un message d'erreur
      // clair à cet endroit plutôt qu'un écran figé ici.
      .catch(() => setState("incomplete"))
    // eslint-disable-next-line react-hooks/exhaustive-deps -- ne doit tourner qu'au montage
  }, [isAuthenticated, accessToken])

  if (!isAuthenticated) {
    return <Navigate to="/signup" replace />
  }
  if (state === "loading") {
    return <p className="p-8 text-center text-sm text-gray-500">Chargement...</p>
  }
  if (state === "incomplete") {
    return <Navigate to="/chercheur/onboarding" replace />
  }
  return <DashboardLayout roleLabel="Chercheur" navItems={CHERCHEUR_NAV_ITEMS} profileTo="/chercheur/profile" />
}

type InvestisseurGateState = "loading" | "incomplete" | InvestorProfileRead

/** Porte d'entrée du dashboard investisseur — même pattern que
 * ChercheurDashboardRoute : fetch le profil une seule fois, redirige vers
 * l'onboarding tant que profile_completion === "0%". Décision actée : même
 * blocage strict que chercheur/entrepreneur, malgré le parcours "sans
 * blocage" évoqué dans le PDF source — au moins un champ (thèse ou email de
 * contact) est requis pour passer l'onboarding, donc jamais "0%" en sortie
 * (voir InvestorOnboardingRequest._at_least_one_field côté backend). */
function InvestisseurDashboardRoute() {
  const { isAuthenticated, accessToken } = useAuth()
  const [state, setState] = useState<InvestisseurGateState>("loading")

  useEffect(() => {
    if (!isAuthenticated || !accessToken) return

    getMyInvestorProfile(accessToken)
      .then((profile) => setState(profile.profile_completion === "0%" ? "incomplete" : profile))
      .catch(() => setState("incomplete"))
    // eslint-disable-next-line react-hooks/exhaustive-deps -- ne doit tourner qu'au montage
  }, [isAuthenticated, accessToken])

  if (!isAuthenticated) {
    return <Navigate to="/signup" replace />
  }
  if (state === "loading") {
    return <p className="p-8 text-center text-sm text-gray-500">Chargement...</p>
  }
  if (state === "incomplete") {
    return <Navigate to="/investisseur/onboarding" replace />
  }
  return <DashboardLayout roleLabel="Investisseur" navItems={EMPTY_NAV_ITEMS} profileTo="/investisseur/profile" />
}

export default function App() {
  return (
    <Routes>
      <Route path="/signup" element={<SignupPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/onboarding" element={<OnboardingRoute />} />
      <Route path="/admin/legal-texts" element={<AdminRoute />} />
      <Route path="/admin/sector-insurance" element={<AdminSectorInsuranceRoute />} />
      <Route path="/chercheur/onboarding" element={<ChercheurOnboardingRoute />} />
      <Route path="/investisseur/onboarding" element={<InvestisseurOnboardingRoute />} />

      <Route path="/entrepreneur" element={<EntrepreneurDashboardRoute />}>
        <Route index element={<Navigate to="mon-projet" replace />} />
        {/* MyProjectLayout fait le fetch project + fieldValues une seule fois pour
            les 7 pages ci-dessous (voir ce fichier) — navigation entre elles sans
            refetch, au lieu d'un GET /projects/me + GET /field-values par page. */}
        <Route path="mon-projet" element={<MyProjectLayout />}>
          <Route index element={<MyProjectPage />} />
          <Route path="informations-generales" element={<ProjectGeneralInfoPage />} />
          <Route path="informations-legales" element={<ProjectLegalInfoPage />} />
          <Route path="equipe-capital" element={<TeamCapitalPage />} />
          <Route path="vitrine-publique" element={<ProjectPublicProfilePage />} />
          <Route path="coffre-fort" element={<DocumentVaultPage />} />
          {/* Service 1.1.13 — moteur de session réutilisé par 1.1.4/statuts avec un
              autre document_type ; project vient du contexte MyProjectLayout, même
              convention que coffre-fort ci-dessus. Route v1 ("pacte-fondateurs") retirée
              (26/09/2026) : v1 supprimé (code + données), une seule version existe. */}
          <Route path="pacte-fondateurs-v2" element={<PacteFondateursV2Page />} />
        </Route>
        {/* Pas sous MyProjectLayout : PlanActionPage fait son propre GET
            /projects/me (voir ce fichier) — son besoin diffère (vérifier
            project_type, pas charger fieldValues). */}
        <Route path="plan-action" element={<PlanActionPage />} />
        <Route path="profile" element={<ProfilePage />} />
      </Route>

      <Route path="/chercheur" element={<ChercheurDashboardRoute />}>
        <Route index element={<Navigate to="profile" replace />} />
        <Route path="profile" element={<ResearcherProfileDetailsPage />} />
        <Route path="travaux" element={<ResearchWorksPage />} />
        <Route path="expertises" element={<PastExpertisesPage />} />
      </Route>

      <Route path="/investisseur" element={<InvestisseurDashboardRoute />}>
        <Route index element={<Navigate to="profile" replace />} />
        <Route path="profile" element={<InvestorProfilePage />} />
      </Route>

      <Route path="/" element={<HomeRoute />} />
    </Routes>
  )
}
