import { apiFetch } from './client'

export interface Artifact {
  id: string
  filename: string
  source_type: string
  status: string
  content: string | null
  metadata_json: string | null
  error: string | null
  created_at: string
  updated_at: string
}

export function listArtifacts(): Promise<Artifact[]> {
  return apiFetch<Artifact[]>('/artifacts')
}

export function getArtifact(id: string): Promise<Artifact> {
  return apiFetch<Artifact>(`/artifacts/${id}`)
}

export function deleteArtifact(id: string): Promise<void> {
  return apiFetch<void>(`/artifacts/${id}`, { method: 'DELETE' })
}
