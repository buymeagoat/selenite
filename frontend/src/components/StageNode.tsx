type Status = 'queued' | 'running' | 'complete' | 'failed'

interface StageNodeProps {
  label: string
  status: Status
}

const STATUS_STYLES: Record<Status, string> = {
  queued:   'text-muted bg-border',
  running:  'text-accent bg-accent/10 ring-1 ring-accent animate-pulse',
  complete: 'text-green-400 bg-green-400/10',
  failed:   'text-red-400 bg-red-400/10',
}

export default function StageNode({ label, status }: StageNodeProps) {
  return (
    <div className={`font-mono text-xs px-3 py-1.5 rounded transition-all ${STATUS_STYLES[status]}`}>
      {label}
    </div>
  )
}
