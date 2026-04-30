import React, { createContext, useContext, useEffect, useState } from 'react'
import { me } from '../api/auth'

interface AuthContextValue {
  authenticated: boolean | null
  setAuthenticated: (v: boolean) => void
}

const AuthContext = createContext<AuthContextValue>({
  authenticated: null,
  setAuthenticated: () => {},
})

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null)

  useEffect(() => {
    me()
      .then(() => setAuthenticated(true))
      .catch(() => setAuthenticated(false))
  }, [])

  return (
    <AuthContext.Provider value={{ authenticated, setAuthenticated }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
