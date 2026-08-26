/**
 * État d'authentification global — stocke les tokens en localStorage (décision
 * actée : simple pour I0, mais vulnérable en cas de faille XSS — à revisiter si
 * le projet passe un jour à des cookies httpOnly côté backend).
 */
import { createContext, useContext, useState, type ReactNode } from "react"
import type { TokenResponse } from "../api/authApi"

const ACCESS_TOKEN_KEY = "wink_access_token"
const REFRESH_TOKEN_KEY = "wink_refresh_token"

interface AuthContextValue {
  accessToken: string | null
  isAuthenticated: boolean
  setTokens: (tokens: TokenResponse) => void
  clearTokens: () => void
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [accessToken, setAccessToken] = useState<string | null>(() => localStorage.getItem(ACCESS_TOKEN_KEY))

  function setTokens(tokens: TokenResponse) {
    localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token)
    localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token)
    setAccessToken(tokens.access_token)
  }

  function clearTokens() {
    localStorage.removeItem(ACCESS_TOKEN_KEY)
    localStorage.removeItem(REFRESH_TOKEN_KEY)
    setAccessToken(null)
  }

  return (
    <AuthContext.Provider value={{ accessToken, isAuthenticated: accessToken !== null, setTokens, clearTokens }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error("useAuth doit être utilisé à l'intérieur d'un <AuthProvider>.")
  }
  return ctx
}

/** Lu directement (hors contexte React) par la logique de logout/refresh, qui
 * n'a pas besoin de re-render sur ce changement. */
export function getStoredRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY)
}
