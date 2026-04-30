import { useState, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { uploadFile } from '../api/upload'
import { listProcessors } from '../api/processors'
import type { Processor } from '../api/processors'

const AUDIO_EXTENSIONS = ['.mp3', '.wav', '.m4a', '.ogg', '.flac', '.mp4', '.webm', '.aac']

function ext(filename: string) {
  return filename.slice(filename.lastIndexOf('.')).toLowerCase()
}

export default function Upload() {
  const navigate = useNavigate()
  const [processors, setProcessors] = useState<Processor[]>([])
  const [asr, setAsr] = useState('faster_whisper_large_v3')
  const [diarizer, setDiarizer] = useState('pyannote_3_1')
  const [dragging, setDragging] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)

  useEffect(() => {
    listProcessors().then(setProcessors).catch(() => {})
  }, [])

  const asrOptions = processors.filter(p => p.processor_type === 'asr')
  const diarizerOptions = processors.filter(p => p.processor_type === 'diarizer')

  const handleFile = (f: File) => {
    if (!AUDIO_EXTENSIONS.includes(ext(f.name))) {
      setError(`Unsupported file type: ${ext(f.name)}`)
      return
    }
    setFile(f)
    setError(null)
  }

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) handleFile(f)
  }, [])

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) handleFile(f)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file) return
    setUploading(true)
    setError(null)
    try {
      await uploadFile(file, asr, diarizer)
      navigate('/queue')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="p-8 max-w-2xl">
      <h1 className="font-serif text-2xl text-text mb-6">Upload</h1>

      <form onSubmit={handleSubmit} className="flex flex-col gap-6">
        <div
          onDragOver={e => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={`border-2 border-dashed rounded-lg p-12 text-center transition-colors cursor-pointer
            ${dragging ? 'border-accent bg-accent/5' : 'border-border hover:border-muted'}`}
          onClick={() => document.getElementById('file-input')?.click()}
        >
          <input id="file-input" type="file" className="hidden" accept={AUDIO_EXTENSIONS.join(',')} onChange={onFileChange} />
          {file ? (
            <div>
              <p className="font-mono text-sm text-accent">{file.name}</p>
              <p className="font-mono text-xs text-muted mt-1">{(file.size / 1024 / 1024).toFixed(1)} MB</p>
            </div>
          ) : (
            <div>
              <p className="text-muted font-mono text-sm">Drop audio file here</p>
              <p className="text-muted font-mono text-xs mt-1">{AUDIO_EXTENSIONS.join(' ')}</p>
            </div>
          )}
        </div>

        {file && (
          <div className="bg-panel border border-border rounded-lg p-4 flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <label className="font-mono text-xs text-muted uppercase tracking-widest">ASR Model</label>
              <select
                value={asr}
                onChange={e => setAsr(e.target.value)}
                className="bg-bg border border-border rounded px-3 py-2 text-text font-mono text-sm focus:outline-none focus:border-accent"
              >
                {asrOptions.length > 0
                  ? asrOptions.map(p => <option key={p.key} value={p.key}>{p.display_name}</option>)
                  : <option value="faster_whisper_large_v3">Faster Whisper Large v3</option>
                }
              </select>
            </div>
            <div className="flex flex-col gap-2">
              <label className="font-mono text-xs text-muted uppercase tracking-widest">Diarizer</label>
              <select
                value={diarizer}
                onChange={e => setDiarizer(e.target.value)}
                className="bg-bg border border-border rounded px-3 py-2 text-text font-mono text-sm focus:outline-none focus:border-accent"
              >
                {diarizerOptions.length > 0
                  ? diarizerOptions.map(p => <option key={p.key} value={p.key}>{p.display_name}</option>)
                  : <option value="pyannote_3_1">Pyannote Speaker Diarization 3.1</option>
                }
              </select>
            </div>
          </div>
        )}

        {error && <p className="text-red-400 font-mono text-sm">{error}</p>}

        <button
          type="submit"
          disabled={!file || uploading}
          className="bg-accent text-bg font-mono text-sm font-semibold py-2 px-6 rounded
                     hover:brightness-110 disabled:opacity-40 disabled:cursor-not-allowed transition-all self-start"
        >
          {uploading ? 'Uploading…' : 'Process'}
        </button>
      </form>
    </div>
  )
}
