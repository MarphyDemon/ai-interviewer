import client from './client'

export interface InviteInfo {
  position: string
  jdTitle: string
  orgName: string
  difficulty: string
  duration: number
  style: string
  note: string
  active: boolean
  expiresAt: string | null
}

export interface InviteStartResult {
  token: string
  candidateName: string
  interviewId: number
  stage: { stage: string; index: number; total: number; label: string; labelEn: string }
  firstQuestion: {
    action: string
    content: string
    reasoning?: string
    choices?: { label: string; intent: string }[]
    problem?: unknown
  }
  config: {
    position: string
    difficulty: string
    duration: number
    style: string
  }
}

/** 读取邀请信息（公开接口，候选人未登录时调用） */
export function getInvite(token: string): Promise<InviteInfo> {
  return client.get(`/invite/${token}`)
}

/** 候选人填写姓名后开始面试，返回可直接使用的登录 token */
export function startByInvite(
  token: string,
  payload: { name: string; email?: string; lang?: string },
): Promise<InviteStartResult> {
  const lang = (localStorage.getItem('lang') as 'en' | 'zh') || 'en'
  return client.post(`/invite/${token}/start`, { ...payload, lang })
}
