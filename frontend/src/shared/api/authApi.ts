/**
 * Client HTTP pour `backend/shared/auth` — un fichier, une responsabilité :
 * parler à l'API d'auth, rien d'autre (pas de state, pas de stockage token ici,
 * voir `shared/context/AuthContext.tsx` pour ça).
 */
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

export type Role = "entrepreneur" | "chercheur" | "investisseur"

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: "bearer"
}

export interface UserRead {
  id: string
  email: string
  first_name: string | null
  last_name: string | null
  role: Role
  created_at: string
}

/** Erreur HTTP normalisée — porte le status pour que l'appelant puisse réagir
 * différemment selon le code (ex: 409 = email déjà pris, 401 = mauvais mdp). */
export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  })

  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      detail = body.detail ?? detail
    } catch {
      // Réponse sans corps JSON exploitable (ex: erreur réseau brute) — on garde statusText.
    }
    throw new ApiError(response.status, detail)
  }

  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

export function signup(data: {
  email: string
  password: string
  role: Role
  first_name: string
  last_name: string
}): Promise<TokenResponse> {
  return request<TokenResponse>("/auth/signup", { method: "POST", body: JSON.stringify(data) })
}

export function signupGoogle(data: { id_token: string; role: Role }): Promise<TokenResponse> {
  return request<TokenResponse>("/auth/signup/google", { method: "POST", body: JSON.stringify(data) })
}

export function login(data: { email: string; password: string }): Promise<TokenResponse> {
  return request<TokenResponse>("/auth/login", { method: "POST", body: JSON.stringify(data) })
}

export function loginGoogle(data: { id_token: string }): Promise<TokenResponse> {
  // Le backend (`GoogleSignupRequest`) exige un champ `role` même pour /login/google,
  // alors qu'il est ignoré côté serveur pour cet endpoint (le rôle vient du compte
  // déjà créé) — conséquence du choix de réutiliser le même schéma pour signup et
  // login Google (voir le commentaire dans auth_router.py). On envoie une valeur
  // fixe pour satisfaire la validation, sans impact réel.
  return request<TokenResponse>("/auth/login/google", {
    method: "POST",
    body: JSON.stringify({ ...data, role: "entrepreneur" satisfies Role }),
  })
}

export function refreshTokens(data: { refresh_token: string }): Promise<TokenResponse> {
  return request<TokenResponse>("/auth/refresh", { method: "POST", body: JSON.stringify(data) })
}

export function logout(data: { refresh_token: string }): Promise<void> {
  return request<void>("/auth/logout", { method: "POST", body: JSON.stringify(data) })
}

export function forgotPassword(data: { email: string }): Promise<{ detail: string }> {
  return request<{ detail: string }>("/auth/forgot-password", { method: "POST", body: JSON.stringify(data) })
}

export function resetPassword(data: { token: string; new_password: string }): Promise<void> {
  return request<void>("/auth/reset-password", { method: "POST", body: JSON.stringify(data) })
}

export function getCurrentUser(accessToken: string): Promise<UserRead> {
  return request<UserRead>("/auth/me", { headers: { Authorization: `Bearer ${accessToken}` } })
}
