import { useEffect, useState } from 'react'
import { listProcessors, Processor } from '../api/processors'

export default function Settings() {
  const [processors, setProcessors] = useState<Processor[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    listProcessors()
      .then(setProcessors)
      .finally(() => setLoading(false))
  }, [])

  const byType = (type: string) => processors.filter((p) => p.processor_type === type)

  return (
    <div className="p-8 max-w-2xl">
      <h1 className="font-serif text-2xl text-text mb-6">Settings</h1>

      {loading ? (
        <p className="text-muted font-mono text-sm">Loading processors…</p>
      ) : (
        <div className="flex flex-col gap-6">
          {(['asr', 'diarizer', 'ocr', 'llm'] as const).map((type) => (
            <div key={type} className="bg-panel border border-border rounded-lg p-4">
              <h2 className="font-mono text-xs uppercase tracking-widest text-muted mb-3">
                {type === 'asr' ? 'ASR Models' :
                 type === 'diarizer' ? 'Diarizers' :
                 type === 'ocr' ? 'OCR Models' : 'LLM Processors'}
              </h2>
              <div className="flex flex-col gap-2">
                {byType(type).map((p) => (
                  <div key={p.key} className="flex items-center justify-between">
                    <span className="font-mono text-sm text-text">{p.display_name}</span>
                    <span
                      className={`font-mono text-xs px-2 py-0.5 rounded ${
                        p.available
                          ? 'text-green-400 bg-green-400/10'
                          : 'text-muted bg-border'
                      }`}
                    >
                      {p.available ? 'available' : 'not installed'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
