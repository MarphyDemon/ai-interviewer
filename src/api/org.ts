import client from './client'

export interface OrgInfo {
  id: number
  name: string
  role: string
  canManage: boolean
  members: OrgMemberRow[]
  inviteCount: number
  candidateCount: number
}

export interface OrgMemberRow {
  userId: number
  username: string
  role: string
  createdAt: string | null
}

export interface InviteRow {
  id: number
  token: string
  position: string
  jdId: number | null
  difficulty: string
  duration: number
  style: string
  note: string
  /** 本次面试的考察重点（HR 自定义） */
  focus: string
  candidateCount: number
  scoredCount: number
  avgScore: number | null
  active: boolean
  expiresAt: string | null
  createdAt: string | null
}

export interface CandidateRow {
  candidateId: number
  name: string
  email: string
  inviteId: number
  position: string
  interviewId: number | null
  status: string
  stage: string | null
  totalScore: number | null
  summary: string
  startedAt: string | null
  endedAt: string | null
  createdAt: string | null
}

export interface CreateInvitePayload {
  position: string
  jdId?: number | null
  difficulty?: string
  duration?: number
  style?: string
  note?: string
  /** 本次面试的考察重点（HR 自定义，注入面试 prompt） */
  focus?: string
  expiresInDays?: number
}

/** 当前用户的组织（不存在则后端自动开通） */
export function getMyOrg(): Promise<OrgInfo> {
  return client.get('/org/me')
}

export function listInvites(): Promise<InviteRow[]> {
  return client.get('/org/invites')
}

export function createInvite(payload: CreateInvitePayload): Promise<{
  id: number
  token: string
  path: string
  position: string
  expiresAt: string | null
}> {
  return client.post('/org/invites', payload)
}

export function revokeInvite(inviteId: number): Promise<{ ok: boolean }> {
  return client.delete(`/org/invites/${inviteId}`)
}

/** 候选人排名（按报告总分倒序） */
export function listCandidates(params: { inviteId?: number; limit?: number } = {}): Promise<CandidateRow[]> {
  return client.get('/org/candidates', { params })
}

export function addMember(username: string, role = 'hr'): Promise<{ ok: boolean }> {
  return client.post('/org/members', { username, role })
}
