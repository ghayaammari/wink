import { Outlet, useLocation } from "react-router-dom"
import { CopilotProvider } from "../../entrepreneur/context/CopilotContext"
import Sidebar, { type SidebarNavItem } from "./Sidebar"

interface DashboardLayoutProps {
  roleLabel: string
  navItems: SidebarNavItem[]
  profileTo: string
  // Copilot conformite (voir CopilotPage.tsx) -- entrepreneur
  // uniquement pour l'instant (Wink_context_project.md section 4 :
  // aucun copilot prevu pour chercheur/investisseur a ce stade). Ce
  // composant partage (DashboardLayout) reste utilise par les 3 acteurs,
  // donc ce prop est optionnel et false par defaut plutot que d'ajouter
  // une variante de layout juste pour ca.
  showCopilot?: boolean
}

// Routes qui doivent utiliser toute la largeur disponible plutôt que la
// colonne centrée par défaut (pensée pour des formulaires d'onboarding en une
// colonne) — voir le commentaire sur FULL_WIDTH_ROUTES ci-dessous pour la
// dette technique assumée ici.
const FULL_WIDTH_ROUTES = ["/entrepreneur/plan-action", "/entrepreneur/copilot"]

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
export default function DashboardLayout({ roleLabel, navItems, profileTo, showCopilot = false }: DashboardLayoutProps) {
  const { pathname } = useLocation()
  const isFullWidth = FULL_WIDTH_ROUTES.includes(pathname)

  const content = (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar roleLabel={roleLabel} navItems={navItems} profileTo={profileTo} />
      <main className="flex-1 overflow-y-auto px-6 py-8">
        <div className={isFullWidth ? "" : "mx-auto max-w-3xl"}>
          <Outlet />
        </div>
      </main>
    </div>
  )

  // CopilotProvider doit englober <Outlet/> : CopilotPage.tsx (l'entrée
  // "Copilot" de la sidebar, voir App.tsx) ET les pages de diagnostic
  // (bouton "Terminer") partagent le meme historique de conversation via
  // useCopilot() -- voir CopilotContext.tsx. N'enveloppe rien pour
  // chercheur/investisseur (showCopilot=false), pas de contexte inutile.
  return showCopilot ? <CopilotProvider>{content}</CopilotProvider> : content
}
