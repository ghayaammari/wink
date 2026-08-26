import { useEffect, useState } from "react"
import { Navigate, Route, Routes } from "react-router-dom"
import OnboardingWizard from "./entrepreneur/components/OnboardingWizard"
import { OnboardingWizardProvider } from "./entrepreneur/context/OnboardingWizardContext"
import MyProjectLayout from "./entrepreneur/pages/MyProjectLayout"
import MyProjectPage from "./entrepreneur/pages/MyProjectPage"
import ProjectGeneralInfoPage from "./entrepreneur/pages/ProjectGeneralInfoPage"
import ProjectLegalInfoPage from "./entrepreneur/pages/ProjectLegalInfoPage"
import ProjectPublicProfilePage from "./entrepreneur/pages/ProjectPublicProfilePage"
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

// Navigation métier de l'entrepreneur — "Mon projet" se déplie en 3
// sous-sections (voir Sidebar.tsx : dépliage automatique selon l'URL, pas de
// bouton toggle séparé). "Mon profil" et la déconnexion sont gérés par
// Sidebar elle-même, pas listés ici.
const ENTREPRENEUR_NAV_ITEMS: SidebarNavItem[] = [
  {
    to: "/entrepreneur/mon-projet",
    label: "Mon projet",
    icon: ICON_PROJECT,
    children: [
      { to: "/entrepreneur/mon-projet/informations-generales", label: "Informations générales" },
      { to: "/entrepreneur/mon-projet/informations-legales", label: "Informations légales" },
      { to: "/entrepreneur/mon-projet/vitrine-publique", label: "Vitrine publique" },
    ],
  },
]

// Chercheur et investisseur n'ont encore aucune section métier construite en
// I0 (voir Wink_architecture_fichiers.md : leurs dossiers backend/frontend
// restent vides hors `entrepreneur_profile`/`researcher_profile`/
// `investor_profile`) — la Sidebar reste identique (même composant), juste
// sans item de navigation métier tant que leur incrément n'en ajoute pas.
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
 * fichier pour la redirection vers /onboarding si `project === null`. */
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

/** Stub minimal — pas encore de service métier construit pour ce rôle en I0
 * (voir EMPTY_NAV_ITEMS) : seuls la Sidebar et "Mon profil" sont fonctionnels
 * dès maintenant, prêts à accueillir la navigation métier du premier
 * incrément Chercheur. */
function ChercheurDashboardRoute() {
  const { isAuthenticated } = useAuth()
  if (!isAuthenticated) {
    return <Navigate to="/signup" replace />
  }
  return <DashboardLayout roleLabel="Chercheur" navItems={EMPTY_NAV_ITEMS} profileTo="/chercheur/profile" />
}

/** Même stub minimal que ChercheurDashboardRoute, pour le rôle Investisseur. */
function InvestisseurDashboardRoute() {
  const { isAuthenticated } = useAuth()
  if (!isAuthenticated) {
    return <Navigate to="/signup" replace />
  }
  return (
    <DashboardLayout roleLabel="Investisseur" navItems={EMPTY_NAV_ITEMS} profileTo="/investisseur/profile" />
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/signup" element={<SignupPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/onboarding" element={<OnboardingRoute />} />

      <Route path="/entrepreneur" element={<EntrepreneurDashboardRoute />}>
        <Route index element={<Navigate to="mon-projet" replace />} />
        {/* MyProjectLayout fait le fetch project + fieldValues une seule fois pour
            les 4 pages ci-dessous (voir ce fichier) — navigation entre elles sans
            refetch, au lieu d'un GET /projects/me + GET /field-values par page. */}
        <Route path="mon-projet" element={<MyProjectLayout />}>
          <Route index element={<MyProjectPage />} />
          <Route path="informations-generales" element={<ProjectGeneralInfoPage />} />
          <Route path="informations-legales" element={<ProjectLegalInfoPage />} />
          <Route path="vitrine-publique" element={<ProjectPublicProfilePage />} />
        </Route>
        <Route path="profile" element={<ProfilePage />} />
      </Route>

      <Route path="/chercheur" element={<ChercheurDashboardRoute />}>
        <Route index element={<Navigate to="profile" replace />} />
        <Route path="profile" element={<ProfilePage />} />
      </Route>

      <Route path="/investisseur" element={<InvestisseurDashboardRoute />}>
        <Route index element={<Navigate to="profile" replace />} />
        <Route path="profile" element={<ProfilePage />} />
      </Route>

      <Route path="/" element={<HomeRoute />} />
    </Routes>
  )
}
