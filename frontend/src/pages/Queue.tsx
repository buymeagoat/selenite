import { useEffect, useState, useRef } from 'react'
import StageNode from '../components/StageNode'

interface JobEvent {
  id: string
  artifact_id: string
  stage: string
  processor: string
  status: 'queued' | 'running' | 'complete' | 'failed'
  progress: number
  error: string | null
}

interface ArtifactJobs {
  artifact_id: string
  jobs: JobEvent[]
}

export default function Queue() {
  const [artifacts, setArtifacts] = useState<ArtifactJobs[]>([])
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    const es = new EventSource('/api/jobs/stream', { withCredentials: true })
    esRef.current = es

    es.onmessage = (e) => {
      const updates: JobEvent[] = JSON.parse(e.data)
      setArtifacts(prev => {
        const map = new Map(prev.map(a => [a.artifact_id, { ...a, jobs: [...a.jobs] }]))
        for (const job of updates) {
          if (!map.has(job.artifact_id)) {
            map.set(job.artifact_id, { artifact_id: job.artifact_id, jobs: [] })
          }
          const entry = map.get(job.artifact_id)!
          const idx = entry.jobs.findIndex(j => j.id === job.id)
          if (idx >= 0) entry.jobs[idx] = job
          else entry.jobs.push(job)
        }
        return Array.from(map.values())
      })
    }

    return () => es.close()
  }, [])

  const stageStatus = (jobs: JobEvent[], stage: string) => {
    const job = jobs.find(j => j.stage === stage)
    return (job?.status ?? 'queued') as 'queued' | 'running' | 'complete' | 'failed'
  }

  return (
    <div className="p-8 max-w-3xl">
      <h1 className="font-serif text-2xl text-text mb-6">Queue</h1>

      {artifacts.length === 0 ? (
        <p className="text-muted font-mono text-sm">No jobs running.</p>
      ) : (
        <div className="flex flex-col gap-4">
          {artifacts.map(({ artifact_id, jobs }) => {
            const failed = jobs.some(j => j.status === 'failed')
            return (
              <div key={artifact_id} className="bg-panel border border-border rounded-lg p-4">
                <p className="font-mono text-xs text-muted mb-3">{artifact_id.slice(0, 8)}…</p>
                <div className="flex items-center gap-2">
                  <StageNode label="ASR" status={stageStatus(jobs, 'asr')} />
                  <span className="text-border">→</span>
                  <StageNode label="Diarize" status={stageStatus(jobs, 'diarize')} />
                  <span className="text-border">→</span>
                  <StageNode
                    label="Done"
                    status={jobs.every(j => j.status === 'complete') ? 'complete' : failed ? 'failed' : 'queued'}
                  />
                </div>
                {failed && (
                  <p className="text-red-400 font-mono text-xs mt-2">
                    {jobs.find(j => j.status === 'failed')?.error}
                  </p>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
