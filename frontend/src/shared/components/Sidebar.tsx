import type { ReactNode } from "react"
import { useState } from "react"
import { NavLink, useLocation, useNavigate } from "react-router-dom"
import { logout } from "../api/authApi"
import { getStoredRefreshToken, useAuth } from "../context/AuthContext"

export interface SidebarNavChild {
  to: string
  label: string
}

export interface SidebarNavItem {
  to: string
  label: string
  icon: ReactNode
  /** Sous-sections en liste déroulante (ex: "Mon projet" → Informations
   * générales/légales, Vitrine publique). Dépliée automatiquement dès que
   * l'URL courante est sous `to` — pas de bouton "replier/déplier" séparé
   * pour rester minimaliste : le groupe s'ouvre quand on y est, se referme
   * quand on le quitte. */
  children?: SidebarNavChild[]
  /** Alternative a `children` pour un contenu deroulant dynamique (pas une
   * liste fixe de routes) -- ex: l'historique des conversations du copilot
   * (voir CopilotSidebarConversations.tsx), qui depend de donnees chargees
   * a l'execution, pas de routes connues a l'avance. Mutuellement exclusif
   * avec `children` : si les deux sont fournis, `renderChildren` gagne.
   * Sidebar.tsx reste generique (partage par les 3 acteurs) : il ne connait
   * rien du copilot, juste un slot de rendu. */
  renderChildren?: () => ReactNode
}

interface SidebarProps {
  roleLabel: string
  navItems: SidebarNavItem[]
  profileTo: string
}

const ICON_PROFILE = (
  <path
    strokeLinecap="round"
    strokeLinejoin="round"
    d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z"
  />
)

const ICON_LOGOUT = (
  <path
    strokeLinecap="round"
    strokeLinejoin="round"
    d="M8.25 9V5.25A2.25 2.25 0 0 1 10.5 3h6a2.25 2.25 0 0 1 2.25 2.25v13.5A2.25 2.25 0 0 1 16.5 21h-6a2.25 2.25 0 0 1-2.25-2.25V15M12 9l-3 3m0 0 3 3m-3-3h12.75"
  />
)

const ICON_CHEVRON = <path strokeLinecap="round" strokeLinejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" />

function NavIcon({ children, className = "h-5 w-5" }: { children: ReactNode; className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      className={`shrink-0 ${className}`}
    >
      {children}
    </svg>
  )
}

/**
 * Sidebar partagée par les 3 acteurs — template de base du dashboard
 * post-onboarding (voir DashboardLayout.tsx pour le shell complet). "Mon
 * profil" et la déconnexion sont communs aux 3 acteurs, donc fixés une fois
 * ici plutôt que répétés dans chaque config de navigation par acteur.
 */
export default function Sidebar({ roleLabel, navItems, profileTo }: SidebarProps) {
  const { clearTokens } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [isSigningOut, setIsSigningOut] = useState(false)

  async function handleSignOut() {
    setIsSigningOut(true)
    const refreshToken = getStoredRefreshToken()
    try {
      if (refreshToken) {
        await logout({ refresh_token: refreshToken })
      }
    } catch {
      // /auth/logout est idempotent côté backend (revoke_refresh_token ne lève
      // jamais si le token est déjà invalide/expiré) — même si l'appel réseau
      // échoue ici, on déconnecte quand même localement : laisser l'utilisateur
      // "connecté" dans ce cas serait pire (même logique que l'ancien HomePage).
    } finally {
      clearTokens()
      navigate("/login")
    }
  }

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
      isActive ? "bg-indigo-50 text-indigo-700" : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
    }`

  const childLinkClass = ({ isActive }: { isActive: boolean }) =>
    `rounded-lg px-3 py-1.5 text-sm transition ${
      isActive ? "bg-indigo-50 font-medium text-indigo-700" : "text-gray-500 hover:bg-gray-50 hover:text-gray-900"
    }`

  return (
    <aside className="flex h-screen w-64 shrink-0 flex-col justify-between border-r border-gray-200 bg-white px-3 py-6">
      <div className="flex flex-col gap-6">
        <div className="px-3">
          <p className="text-lg font-semibold text-gray-900">Wink</p>
          <p className="text-xs text-gray-400">{roleLabel}</p>
        </div>

        {navItems.length > 0 && (
          <nav className="flex flex-col gap-1">
            {navItems.map((item) => {
              const isGroupOpen = Boolean(item.children ?? item.renderChildren) && location.pathname.startsWith(item.to)
              return (
                <div key={item.to} className="flex flex-col gap-1">
                  <NavLink to={item.to} className={linkClass}>
                    <NavIcon>{item.icon}</NavIcon>
                    <span className="flex-1">{item.label}</span>
                    {(item.children ?? item.renderChildren) && (
                      <NavIcon className={`h-4 w-4 transition-transform ${isGroupOpen ? "rotate-90" : ""}`}>
                        {ICON_CHEVRON}
                      </NavIcon>
                    )}
                  </NavLink>

                  {isGroupOpen && item.renderChildren && item.renderChildren()}

                  {isGroupOpen && !item.renderChildren && item.children && (
                    <div className="ml-4 flex flex-col gap-0.5 border-l border-gray-100 pl-4">
                      {item.children.map((child) => (
                        <NavLink key={child.to} to={child.to} className={childLinkClass}>
                          {child.label}
                        </NavLink>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </nav>
        )}
      </div>

      <div className="flex flex-col gap-1 border-t border-gray-100 pt-3">
        <NavLink to={profileTo} className={linkClass}>
          <NavIcon>{ICON_PROFILE}</NavIcon>
          Mon profil
        </NavLink>
        <button
          type="button"
          onClick={handleSignOut}
          disabled={isSigningOut}
          className="flex items-center gap-3 rounded-lg px-3 py-2 text-left text-sm font-medium text-gray-600 transition hover:bg-red-50 hover:text-red-600 disabled:opacity-50"
        >
          <NavIcon>{ICON_LOGOUT}</NavIcon>
          {isSigningOut ? "Déconnexion..." : "Se déconnecter"}
        </button>
      </div>
    </aside>
  )
}
