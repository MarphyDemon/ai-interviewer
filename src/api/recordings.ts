import client from './client'

export interface RecordingItem {
  id: number
  streamType: string
  fileSize: number
  durationMs: number
  mimeType: string
  url: string
  createdAt: string | null
}

export function getRecordings(interviewId: number): Promise<RecordingItem[]> {
  return client.get(`/recordings/${interviewId}`)
}

export function deleteRecording(interviewId: number, recordingId: number): Promise<{ ok: boolean }> {
  return client.delete(`/recordings/${interviewId}/${recordingId}`)
}

export function uploadRecording(
  interviewId: number,
  blob: Blob,
  streamType: string = 'audio',
): Promise<{ id: number; url: string; fileSize: number; mimeType: string }> {
  const formData = new FormData()
  formData.append('file', blob, `recording_${Date.now()}.webm`)
  formData.append('stream_type', streamType)
  return client.post(`/recordings/upload/${interviewId}?stream_type=${streamType}`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}