import { useEffect, useState } from "react"
import { Navigate, Route, Routes } from "react-router-dom"
import LegalTextsValidationPage from "./admin/pages/LegalTextsValidationPage"
import SectorInsuranceValidationPage from "./admin/pages/SectorInsuranceValidationPage"
import AdministrativeGuidesValidationPage from "./admin/pages/AdministrativeGuidesValidationPage"
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
import CompliancePlanPage from "./entrepreneur/pages/CompliancePlanPage"
import CertificationSecnumcloudPage from "./entrepreneur/pages/CertificationSecnumcloudPage"
import CopilotPage from "./entrepreneur/pages/CopilotPage"
import PitchDeckPage from "./entrepreneur/pages/PitchDeckPage"
import CopilotSidebarConversations from "./entrepreneur/components/copilot/CopilotSidebarConversations"
import RgpdDiagnosticPage from "./entrepreneur/pages/RgpdDiagnosticPage"
import AipdAnalysisPage from "./entrepreneur/pages/AipdAnalysisPage"
import AiActDiagnosticPage from "./entrepreneur/pages/AiActDiagnosticPage"
import SectorDiagnosticPage from "./entrepreneur/pages/SectorDiagnosticPage"
import PlanActionPage from "./entrepreneur/pages/PlanActionPage"
import ProjectGeneralInfoPage from "./entrepreneur/pages/ProjectGeneralInfoPage"
import ProjectLegalInfoPage from "./entrepreneur/pages/ProjectLegalInfoPage"
import ProjectPublicProfilePage from "./entrepreneur/pages/ProjectPublicProfilePage"
import TeamCapitalPage from "./entrepreneur/pages/TeamCapitalPage"
import ResearchNeedsPage from "./entrepreneur/pages/ResearchNeedsPage"
import RecommandationsInteressantesPage from "./entrepreneur/pages/RecommandationsInteressantesPage"
import InvestmentOpportunitiesPage from "./entrepreneur/pages/InvestmentOpportunitiesPage"
import InterestingOffersPage from "./entrepreneur/pages/InterestingOffersPage"
import InvestmentOffersPage from "./investisseur/pages/InvestmentOffersPage"
import InvestmentOfferDetailPage from "./investisseur/pages/InvestmentOfferDetailPage"
import InterestingStartupsPage from "./investisseur/pages/InterestingStartupsPage"
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
// Icone "bouclier" -- nav "Conformite" cote entrepreneur (2e plan d'action,
// EPIC-03). Distincte de ICON_CHECKLIST (roadmap EPIC-01) : conformite
// reglementaire, pas une checklist de creation.
const ICON_SHIELD = (
  <path
    strokeLinecap="round"
    strokeLinejoin="round"
    d="M9 12.75 11.25 15 15 9.75M12 3c-2.755 0-5.455.232-8.083.678-.795.134-1.417.79-1.417 1.615V9.75c0 5.19 3.045 9.673 7.5 11.75 4.455-2.077 7.5-6.56 7.5-11.75V5.293c0-.825-.622-1.48-1.417-1.615A48.09 48.09 0 0 0 12 3Z"
  />
)

// Icone "bulle de chat" -- nav "Copilot" cote entrepreneur (entree de
// premier niveau comme Plan d'action/Conformite, pas un widget flottant a
// part, voir CopilotPage.tsx).
const ICON_CHAT = (
  <path
    strokeLinecap="round"
    strokeLinejoin="round"
    d="M8.625 12a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm3.75 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm3.75 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0ZM21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 0 1-2.555-.337A5.972 5.972 0 0 1 5.41 20.97a5.969 5.969 0 0 1-.474-.065 4.48 4.48 0 0 0 .978-2.025c.09-.457-.133-.901-.5-1.185A8.959 8.959 0 0 1 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25Z"
  />
)

// Icone "graphique de presentation" -- nav "Pitch deck" cote entrepreneur
// (service 6.6.2, EPIC-06/I5).
const ICON_PITCH = (
  <path
    strokeLinecap="round"
    strokeLinejoin="round"
    d="M3.75 5.25h16.5M3.75 5.25v10.5a1.5 1.5 0 0 0 1.5 1.5h4.5m-6-12h16.5m0 0v10.5a1.5 1.5 0 0 1-1.5 1.5h-4.5m-6 0-1.5 3.75m7.5-3.75 1.5 3.75m-9 0h10.5M9 12.75l2.25-2.25 2.25 1.5 3-3"
  />
)

// Icone "loupe" -- nav "Besoins scientifiques" cote entrepreneur (service
// 7.7.1, depot de besoin scientifique / expertise, base du matching Startup
// <-> Chercheur, EPIC-07). Renommee le 27/09/2026 (etait "Recherche",
// confondu avec une fonction de recherche/moteur -- le nom decrit
// maintenant l'action de l'entrepreneur, pas le mecanisme). Distincte de
// ICON_CHECKLIST/ICON_SHIELD : espace de matching, pas une checklist ni de
// la conformite.
const ICON_SEARCH = (
  <path
    strokeLinecap="round"
    strokeLinejoin="round"
    d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z"
  />
)

// Icone "porte-documents ouvert" -- nav "Mes offres" cote investisseur
// (offres de financement deposees, matching Offre -> Startup, miroir de
// ICON_SEARCH cote entrepreneur). Reutilise ICON_BRIEFCASE serait ambigu
// (deja utilisee pour "Mes expertises" chercheur, semantique differente) --
// icone dediee "tag prix / offre" pour rester distincte.
const ICON_OFFERS = (
  <path
    strokeLinecap="round"
    strokeLinejoin="round"
    d="M21 11.25v8.25a1.5 1.5 0 0 1-1.5 1.5H4.5a1.5 1.5 0 0 1-1.5-1.5v-8.25M12 4.875A2.625 2.625 0 1 0 9.375 7.5H12m0-2.625V7.5m0-2.625A2.625 2.625 0 1 1 14.625 7.5H12m0 0V21m-8.625-9.75h17.25c.621 0 1.125-.504 1.125-1.125v-2.25c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v2.25c0 .621.504 1.125 1.125 1.125Z"
  />
)

// Icone "tendance haussiere" -- nav "Investissement" cote entrepreneur
// (service EPIC-06 6.6.1, feed de matching Startup -> Offres, sens inverse
// de ICON_OFFERS cote investisseur). Distincte de ICON_SEARCH (matching
// chercheur) : espace de matching investissement, pas de recherche.
const ICON_INVESTMENT = (
  <path
    strokeLinecap="round"
    strokeLinejoin="round"
    d="M2.25 18 9 11.25l4.306 4.306a11.95 11.95 0 0 1 5.814-5.518l2.74-1.22m0 0-5.94-2.281m5.94 2.28-2.28 5.941"
  />
)

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
    ],
  },
  { to: "/entrepreneur/plan-action", label: "Plan d'action", icon: ICON_CHECKLIST },
  { to: "/entrepreneur/conformite", label: "Conformite", icon: ICON_SHIELD },
  {
    to: "/entrepreneur/recherche",
    label: "Besoins scientifiques",
    icon: ICON_SEARCH,
    children: [
      { to: "/entrepreneur/recherche", label: "Mes besoins" },
      { to: "/entrepreneur/recherche/interessantes", label: "Recommandations intéressantes" },
    ],
  },
  {
    to: "/entrepreneur/investissement",
    label: "Investissement",
    icon: ICON_INVESTMENT,
    children: [
      { to: "/entrepreneur/investissement", label: "Offres" },
      { to: "/entrepreneur/investissement/interessantes", label: "Offres intéressantes" },
    ],
  },
  {
    to: "/entrepreneur/copilot",
    label: "Copilot",
    icon: ICON_CHAT,
    renderChildren: () => <CopilotSidebarConversations />,
  },
  { to: "/entrepreneur/pitch-deck", label: "Pitch deck", icon: ICON_PITCH },
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

// Investisseur : "Mes offres" (service matching Offre -> Startup, miroir de
// "Besoins scientifiques" cote entrepreneur) -- offres de financement deposees et,
// sous-section, les startups marquees "interessantes" toutes offres
// confondues (voir InterestingStartupsPage). Le profil (these, email de
// contact, organisation) reste fusionne avec "Mon profil"
// (profileTo="/investisseur/profile"), pas d'entree separee ici.
const INVESTISSEUR_NAV_ITEMS: SidebarNavItem[] = [
  {
    to: "/investisseur/offres",
    label: "Mes offres",
    icon: ICON_OFFERS,
    children: [
      { to: "/investisseur/offres", label: "Mes offres" },
      { to: "/investisseur/offres/interessantes", label: "Startups intéressantes" },
    ],
  },
]

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

function AdminAdministrativeGuidesRoute() {
  const { isAuthenticated } = useAuth()
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }
  return <AdministrativeGuidesValidationPage />
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
      showCopilot
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
  return <DashboardLayout roleLabel="Investisseur" navItems={INVESTISSEUR_NAV_ITEMS} profileTo="/investisseur/profile" />
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
      <Route path="/admin/administrative-guides" element={<AdminAdministrativeGuidesRoute />} />
      <Route path="/chercheur/onboarding" element={<ChercheurOnboardingRoute />} />
      <Route path="/investisseur/onboarding" element={<InvestisseurOnboardingRoute />} />

      <Route path="/entrepreneur" element={<EntrepreneurDashboardRoute />}>
        <Route index element={<Navigate to="mon-projet" replace />} />
        {/* MyProjectLayout fait le fetch project + fieldValues une seule fois pour
            les 6 pages ci-dessous (voir ce fichier) — navigation entre elles sans
            refetch, au lieu d'un GET /projects/me + GET /field-values par page. */}
        <Route path="mon-projet" element={<MyProjectLayout />}>
          <Route index element={<MyProjectPage />} />
          <Route path="informations-generales" element={<ProjectGeneralInfoPage />} />
          <Route path="informations-legales" element={<ProjectLegalInfoPage />} />
          <Route path="equipe-capital" element={<TeamCapitalPage />} />
          <Route path="vitrine-publique" element={<ProjectPublicProfilePage />} />
          <Route path="coffre-fort" element={<DocumentVaultPage />} />
        </Route>
        {/* Pas sous MyProjectLayout : PlanActionPage fait son propre GET
            /projects/me (voir ce fichier) — son besoin diffère (vérifier
            project_type, pas charger fieldValues). */}
        <Route path="plan-action" element={<PlanActionPage />} />
        <Route path="conformite" element={<CompliancePlanPage />} />
        <Route path="recherche" element={<ResearchNeedsPage />} />
        <Route path="recherche/interessantes" element={<RecommandationsInteressantesPage />} />
        <Route path="investissement" element={<InvestmentOpportunitiesPage />} />
        <Route path="investissement/interessantes" element={<InterestingOffersPage />} />
        <Route path="conformite/rgpd" element={<RgpdDiagnosticPage />} />
        <Route path="conformite/aipd" element={<AipdAnalysisPage />} />
        <Route path="conformite/ai-act" element={<AiActDiagnosticPage />} />
        <Route path="conformite/secteur" element={<SectorDiagnosticPage />} />
        <Route path="conformite/certification-secnumcloud" element={<CertificationSecnumcloudPage />} />
        <Route path="copilot" element={<CopilotPage />} />
        <Route path="pitch-deck" element={<PitchDeckPage />} />
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
        <Route path="offres" element={<InvestmentOffersPage />} />
        <Route path="offres/interessantes" element={<InterestingStartupsPage />} />
        <Route path="offres/:offerId" element={<InvestmentOfferDetailPage />} />
      </Route>

      <Route path="/" element={<HomeRoute />} />
    </Routes>
  )
}
