import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getArtifact, deleteArtifact } from '../api/artifacts'
import type { Artifact } from '../api/artifacts'

export default function ArtifactDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [artifact, setArtifact] = useState<Artifact | null>(null)
  const [loading, setLoading] = useState(true)
  const [rawMode, setRawMode] = useState(false)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    if (!id) return
    getArtifact(id)
      .then(setArtifact)
      .finally(() => setLoading(false))
  }, [id])

  const handleDelete = async () => {
    if (!artifact || !confirm('Delete this artifact?')) return
    setDeleting(true)
    await deleteArtifact(artifact.id)
    navigate('/library')
  }

  if (loading) return <div className="p-8"><p className="text-muted font-mono text-sm">Loading…</p></div>
  if (!artifact) return <div className="p-8"><p className="text-muted font-mono text-sm">Not found.</p></div>

  const meta = artifact.metadata_json ? JSON.parse(artifact.metadata_json) : {}

  return (
    <div className="p-8 max-w-3xl">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="font-serif text-2xl text-text mb-1">{artifact.filename}</h1>
          <div className="flex gap-4 font-mono text-xs text-muted">
            <span>{artifact.source_type}</span>
            {meta.duration && <span>{Math.round(meta.duration)}s</span>}
            {meta.speaker_count && <span>{meta.speaker_count} speakers</span>}
            {meta.language && <span>{meta.language}</span>}
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setRawMode(r => !r)}
            className="font-mono text-xs text-muted hover:text-text border border-border rounded px-3 py-1.5 transition-colors"
          >
            {rawMode ? 'Preview' : 'Raw'}
          </button>
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="font-mono text-xs text-red-400 hover:text-red-300 border border-red-400/30 rounded px-3 py-1.5 transition-colors disabled:opacity-40"
          >
            Delete
          </button>
        </div>
      </div>

      {artifact.status === 'failed' && (
        <div className="bg-red-400/10 border border-red-400/30 rounded p-3 mb-4">
          <p className="font-mono text-xs text-red-400">{artifact.error}</p>
        </div>
      )}

      {artifact.content ? (
        rawMode ? (
          <textarea
            readOnly
            value={artifact.content}
            className="w-full h-96 bg-bg border border-border rounded p-4 font-mono text-sm text-text resize-y focus:outline-none"
          />
        ) : (
          <div className="prose prose-invert prose-sm max-w-none font-mono text-sm text-text whitespace-pre-wrap bg-panel border border-border rounded p-4">
            {artifact.content}
          </div>
        )
      ) : (
        <p className="text-muted font-mono text-sm">
          {artifact.status === 'processing' ? 'Processing…' : 'No content.'}
        </p>
      )}
    </div>
  )
}
