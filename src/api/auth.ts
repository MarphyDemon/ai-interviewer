import client from './client'
import type { UserInfo } from '@/types'

export function register(
  username: string,
  password: string,
  orgName?: string,
): Promise<{ token: string; user: UserInfo }> {
  return client.post('/auth/register', { username, password, orgName: orgName || '' })
}

export function login(
  username: string,
  password: string,
): Promise<{ token: string; user: UserInfo }> {
  return client.post('/auth/login', { username, password })
}

export function getMe(): Promise<UserInfo> {
  return client.get('/auth/me')
}
