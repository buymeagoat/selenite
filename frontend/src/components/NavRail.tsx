import { NavLink, useNavigate } from 'react-router-dom'
import { logout } from '../api/auth'
import { useAuth } from '../hooks/useAuth'

interface NavItem {
  to: string
  label: string
  icon: string
}

const NAV_ITEMS: NavItem[] = [
  { to: '/upload', label: 'Upload', icon: '↑' },
  { to: '/queue', label: 'Queue', icon: '⋯' },
  { to: '/library', label: 'Library', icon: '▤' },
  { to: '/settings', label: 'Settings', icon: '⚙' },
]

export default function NavRail() {
  const { setAuthenticated } = useAuth()
  const navigate = useNavigate()

  async function handleLogout() {
    await logout()
    setAuthenticated(false)
    navigate('/login')
  }

  return (
    <nav className="flex flex-col w-16 min-h-screen bg-panel border-r border-border py-6 items-center gap-1 shrink-0">
      <div className="mb-6">
        <span className="font-serif text-accent text-lg">S</span>
      </div>

      {NAV_ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          className={({ isActive }) =>
            `flex flex-col items-center gap-1 w-full py-3 px-1 text-center transition-colors
             ${isActive
               ? 'text-accent border-r-2 border-accent'
               : 'text-muted hover:text-text'
             }`
          }
        >
          <span className="text-lg leading-none">{item.icon}</span>
          <span className="text-[9px] font-mono uppercase tracking-widest">{item.label}</span>
        </NavLink>
      ))}

      <div className="mt-auto">
        <button
          onClick={handleLogout}
          className="flex flex-col items-center gap-1 w-full py-3 px-1 text-muted hover:text-text transition-colors"
        >
          <span className="text-lg leading-none">⏏</span>
          <span className="text-[9px] font-mono uppercase tracking-widest">Out</span>
        </button>
      </div>
    </nav>
  )
}
