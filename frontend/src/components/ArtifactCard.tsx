import { Link } from 'react-router-dom'
import type { Artifact } from '../api/artifacts'

export default function ArtifactCard({ artifact }: { artifact: Artifact }) {
  const date = new Date(artifact.created_at).toLocaleDateString()
  const statusColor = {
    complete: 'text-green-400',
    processing: 'text-accent',
    failed: 'text-red-400',
    pending: 'text-muted',
  }[artifact.status] ?? 'text-muted'

  return (
    <Link
      to={`/library/${artifact.id}`}
      className="block bg-panel border border-border rounded-lg p-4 hover:border-muted transition-colors"
    >
      <p className="font-mono text-sm text-text truncate mb-1">{artifact.filename}</p>
      <div className="flex items-center gap-3 mt-2">
        <span className="font-mono text-xs text-muted">{artifact.source_type}</span>
        <span className={`font-mono text-xs ${statusColor}`}>{artifact.status}</span>
        <span className="font-mono text-xs text-muted ml-auto">{date}</span>
      </div>
    </Link>
  )
}
