import { apiFetch } from './client'

export interface Processor {
  key: string
  display_name: string
  processor_type: 'asr' | 'diarizer' | 'ocr' | 'llm'
  available: boolean
}

export function listProcessors(): Promise<Processor[]> {
  return apiFetch<Processor[]>('/processors')
}
