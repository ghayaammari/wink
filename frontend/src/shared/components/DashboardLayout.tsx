import { Outlet } from "react-router-dom"
import Sidebar, { type SidebarNavItem } from "./Sidebar"

interface DashboardLayoutProps {
  roleLabel: string
  navItems: SidebarNavItem[]
  profileTo: string
}

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
 */
export default function DashboardLayout({ roleLabel, navItems, profileTo }: DashboardLayoutProps) {
  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar roleLabel={roleLabel} navItems={navItems} profileTo={profileTo} />
      <main className="flex-1 overflow-y-auto px-8 py-10">
        <div className="mx-auto max-w-3xl">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
