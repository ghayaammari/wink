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

/** Body de PATCH /auth/me — tous les champs optionnels. current_password
 * n'est requis que si email est fourni et diffère de l'email actuel (voir
 * auth_service.update_user côté backend). */
export interface UserUpdateRequest {
  first_name?: string
  last_name?: string
  email?: string
  current_password?: string
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

/** `detail` d'une réponse d'erreur FastAPI : soit une chaîne (nos erreurs
 * métier, voir _handle_error/_handle_project_error côté backend), soit un
 * tableau d'erreurs de validation Pydantic — cas d'un 422 (ex: SIRET qui ne
 * respecte pas le pattern `^\d{14}$`), format `[{loc, msg, type}, ...]`.
 *
 * Sans cette conversion, `new ApiError(status, detail)` avec `detail` = ce
 * tableau finissait affiché "[object Object]" à l'écran (`Error` convertit un
 * non-string via son `toString()`) — bug réel rencontré sur la mise à jour du
 * profil légal. Exportée pour être réutilisée par les autres clients API
 * (voir `entrepreneur/api/projectApi.ts`), plutôt que dupliquer cette
 * conversion dans chaque fichier `*Api.ts`. */
export function parseErrorDetail(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => (item && typeof item === "object" && "msg" in item ? String(item.msg) : null))
      .filter((msg): msg is string => msg !== null)
    if (messages.length > 0) return messages.join(" / ")
  }
  return fallback
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
      detail = parseErrorDetail(body.detail, detail)
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

export function updateCurrentUser(accessToken: string, data: UserUpdateRequest): Promise<UserRead> {
  return request<UserRead>("/auth/me", {
    method: "PATCH",
    headers: { Authorization: `Bearer ${accessToken}` },
    body: JSON.stringify(data),
  })
}