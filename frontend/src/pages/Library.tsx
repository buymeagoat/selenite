import { useEffect, useState } from 'react'
import { listArtifacts } from '../api/artifacts'
import type { Artifact } from '../api/artifacts'
import ArtifactCard from '../components/ArtifactCard'

export default function Library() {
  const [artifacts, setArtifacts] = useState<Artifact[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    listArtifacts()
      .then(setArtifacts)
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="p-8">
      <h1 className="font-serif text-2xl text-text mb-6">Library</h1>
      {loading ? (
        <p className="text-muted font-mono text-sm">Loading…</p>
      ) : artifacts.length === 0 ? (
        <p className="text-muted font-mono text-sm">No artifacts yet.</p>
      ) : (
        <div className="grid grid-cols-1 gap-3 max-w-2xl">
          {artifacts.map(a => <ArtifactCard key={a.id} artifact={a} />)}
        </div>
      )}
    </div>
  )
}
