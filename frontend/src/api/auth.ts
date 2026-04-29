import { apiFetch } from './client'

export interface AuthStatus {
  authenticated: boolean
}

export function login(password: string): Promise<AuthStatus> {
  return apiFetch<AuthStatus>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ password }),
  })
}

export function logout(): Promise<AuthStatus> {
  return apiFetch<AuthStatus>('/auth/logout', { method: 'POST' })
}

export function me(): Promise<AuthStatus> {
  return apiFetch<AuthStatus>('/auth/me')
}
