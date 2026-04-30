export interface UploadResponse {
  artifact_id: string
  asr_job_id: string
  diarize_job_id: string
}

export async function uploadFile(
  file: File,
  asrProcessor: string,
  diarizerProcessor: string,
): Promise<UploadResponse> {
  const form = new FormData()
  form.append('file', file)
  form.append('asr_processor', asrProcessor)
  form.append('diarizer_processor', diarizerProcessor)

  const response = await fetch('/api/upload', {
    method: 'POST',
    credentials: 'include',
    body: form,
  })

  if (response.status === 401) {
    window.location.href = '/login'
    throw new Error('Unauthenticated')
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(body.detail ?? 'Upload failed')
  }
  return response.json()
}
