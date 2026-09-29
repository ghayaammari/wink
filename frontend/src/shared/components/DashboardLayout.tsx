import { Outlet, useLocation } from "react-router-dom"
import CopilotFloatingBubble from "../../entrepreneur/components/copilot/CopilotFloatingBubble"
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
 *
 * CORRECTIF du 26/09/2026 : conteneur racine passé de `min-h-screen` a
 * `h-screen overflow-hidden`. Avec `min-h-screen`, des que le contenu d'une
 * page depassait la hauteur de l'ecran, c'est TOUTE la fenetre qui scrollait
 * (le `overflow-y-auto` de <main> ne servait a rien, sa hauteur n'etant
 * jamais bornee) -- et la Sidebar (h-screen mais ni sticky ni fixed)
 * scrollait avec, laissant seulement son bas ("Mon profil"/"Se deconnecter")
 * visible. Desormais le conteneur racine est borne a la hauteur de l'ecran :
 * seul <main> scrolle en interne, la Sidebar reste fixe.
 */
export default function DashboardLayout({ roleLabel, navItems, profileTo, showCopilot = false }: DashboardLayoutProps) {
  const { pathname } = useLocation()
  const isFullWidth = FULL_WIDTH_ROUTES.includes(pathname)

  const content = (
    <div className="flex h-screen overflow-hidden bg-gray-50">
      <Sidebar roleLabel={roleLabel} navItems={navItems} profileTo={profileTo} />
      <main className="flex-1 overflow-y-auto px-6 py-8">
        <div className={isFullWidth ? "" : "mx-auto max-w-3xl"}>
          <Outlet />
        </div>
      </main>
    </div>
  )

  // CopilotProvider doit englober <Outlet/> ET la bulle flottante :
  // CopilotPage.tsx (l'entrée "Copilot" de la sidebar, voir App.tsx), les
  // pages de diagnostic (bouton "Terminer") et CopilotFloatingBubble.tsx
  // partagent le meme historique de conversation via useCopilot() -- voir
  // CopilotContext.tsx. La bulle est rendue a cote de <Outlet/> (pas dans
  // Sidebar.tsx) pour rester au-dessus de TOUTE page entrepreneur, y
  // compris en FULL_WIDTH_ROUTES. N'enveloppe rien pour chercheur/
  // investisseur (showCopilot=false), pas de contexte ni de bulle inutiles.
  return showCopilot ? (
    <CopilotProvider>
      {content}
      <CopilotFloatingBubble />
    </CopilotProvider>
  ) : (
    content
  )
}
