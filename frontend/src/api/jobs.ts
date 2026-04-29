import { apiFetch } from './client'

export interface Job {
  id: string
  artifact_id: string
  stage: string
  stage_task: string | null
  processor: string
  status: string
  progress: number
  error: string | null
  created_at: string
  updated_at: string
}

export function listJobs(): Promise<Job[]> {
  return apiFetch<Job[]>('/jobs')
}

export function getJob(id: string): Promise<Job> {
  return apiFetch<Job>(`/jobs/${id}`)
}
