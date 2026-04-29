import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login } from '../api/auth'
import { useAuth } from '../hooks/useAuth'

export default function Login() {
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const { setAuthenticated } = useAuth()
  const navigate = useNavigate()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      await login(password)
      setAuthenticated(true)
      navigate('/')
    } catch {
      setError('Invalid password')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center">
      <div className="w-full max-w-sm">
        <h1 className="font-serif text-3xl text-text mb-2 text-center">Selenite</h1>
        <p className="text-muted text-sm text-center mb-8 font-mono">ingestion appliance</p>

        <form
          onSubmit={handleSubmit}
          className="bg-panel border border-border rounded-lg p-8 flex flex-col gap-4"
        >
          <div className="flex flex-col gap-2">
            <label htmlFor="password" className="text-sm text-muted font-mono uppercase tracking-widest">
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoFocus
              className="bg-bg border border-border rounded px-3 py-2 text-text font-mono text-sm
                         focus:outline-none focus:border-accent transition-colors"
            />
          </div>

          {error && (
            <p className="text-red-400 text-sm font-mono">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading || !password}
            className="bg-accent text-bg font-mono text-sm font-semibold py-2 px-4 rounded
                       hover:brightness-110 disabled:opacity-40 disabled:cursor-not-allowed
                       transition-all"
          >
            {loading ? 'Authenticating…' : 'Enter'}
          </button>
        </form>
      </div>
    </div>
  )
}
