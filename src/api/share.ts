import client from './client'

export interface SharedReport {
  id: number
  position: string
  difficulty: string
  score: number
  questions: { question: string; answer: string; score: number; feedback?: string }[]
  suggestions: string
  summary: string
}

export function getSharedReport(token: string): Promise<SharedReport> {
  return client.get(`/share/${token}`)
}