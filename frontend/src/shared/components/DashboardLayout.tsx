import { Outlet, useLocation } from "react-router-dom"
import Sidebar, { type SidebarNavItem } from "./Sidebar"

interface DashboardLayoutProps {
  roleLabel: string
  navItems: SidebarNavItem[]
  profileTo: string
}

// Routes qui doivent utiliser toute la largeur disponible plutôt que la
// colonne centrée par défaut (pensée pour des formulaires d'onboarding en une
// colonne) — voir le commentaire sur FULL_WIDTH_ROUTES ci-dessous pour la
// dette technique assumée ici.
const FULL_WIDTH_ROUTES = ["/entrepreneur/plan-action"]

/**
 * Template de base du dashboard, commun aux 3 acteurs — élément de route
 * parent (voir App.tsx : EntrepreneurDashboardRoute/ChercheurDashboardRoute/
 * InvestisseurDashboardRoute) avec un <Outlet/> pour le contenu propre à
 * chaque page enfant (ex: MyProjectPage pour l'entrepreneur).
 *
 * navItems vide = dashboard minimal (chercheur/investisseur tant que leurs
 * incréments ne construisent pas encore de section métier) : la Sidebar reste
 * identique dans les deux cas, "Mon profil" et la déconnexion restent
 * disponibles — voir Sidebar.tsx.
 *
 * Largeur du contenu : `max-w-3xl` par défaut (colonne centrée, adaptée aux
 * formulaires d'onboarding), sauf pour les routes listées dans
 * `FULL_WIDTH_ROUTES` (ex: Plan d'action, dont le graphe de dépendances a
 * besoin de toute la largeur). Dette technique assumée : ce test sur
 * `pathname` est le moyen le plus simple d'exempter UNE route sans toucher à
 * chacune des ~15 pages existantes ; s'il faut un jour plus d'une exception,
 * remplacer par une métadonnée de route (`handle` + `useMatches()`) plutôt
 * que d'allonger cette liste au cas par cas.
 */
export default function DashboardLayout({ roleLabel, navItems, profileTo }: DashboardLayoutProps) {
  const { pathname } = useLocation()
  const isFullWidth = FULL_WIDTH_ROUTES.includes(pathname)

  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar roleLabel={roleLabel} navItems={navItems} profileTo={profileTo} />
      <main className="flex-1 overflow-y-auto px-6 py-8">
        <div className={isFullWidth ? "" : "mx-auto max-w-3xl"}>
          <Outlet />
        </div>
      </main>
    </div>
  )
}
