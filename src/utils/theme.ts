/**
 * 主题色（主色调）切换：通过 CSS 变量驱动 Tailwind 的 primary / accent 色板。
 * 变量定义见 src/style.css，各方案 id 与 [data-theme='<id>'] 选择器一一对应。
 */
export interface ThemeColorOption {
  id: string
  label: string
  /** 设置页色块预览用，与 style.css 中该方案的 primary-500 / accent-500 一致 */
  primary: string
  accent: string
}

export const THEME_COLORS: ThemeColorOption[] = [
  { id: 'indigo', label: '靛蓝', primary: '#6366f1', accent: '#8b5cf6' },
  { id: 'emerald', label: '翡翠绿', primary: '#10b981', accent: '#14b8a6' },
  { id: 'rose', label: '玫红', primary: '#f43f5e', accent: '#ec4899' },
  { id: 'amber', label: '琥珀橙', primary: '#f59e0b', accent: '#f97316' },
]

export const DEFAULT_THEME_COLOR = 'indigo'

const STORAGE_KEY = 'theme_color'

/** 归一化主题色 id：非法值（含历史遗留的 light / dark）一律回落到默认方案 */
export function normalizeThemeColor(id?: string | null): string {
  return THEME_COLORS.some((c) => c.id === id) ? (id as string) : DEFAULT_THEME_COLOR
}

/** 应用主题色：写入 <html data-theme>，并本地记忆以便首屏（未登录时）复用 */
export function applyThemeColor(id?: string | null) {
  const valid = normalizeThemeColor(id)
  if (typeof document !== 'undefined') {
    document.documentElement.dataset.theme = valid
  }
  try {
    localStorage.setItem(STORAGE_KEY, valid)
  } catch {
    // 隐私模式下 localStorage 不可用时忽略
  }
}

/** 读取本地记忆的主题色 */
export function getThemeColor(): string {
  try {
    return normalizeThemeColor(localStorage.getItem(STORAGE_KEY))
  } catch {
    return DEFAULT_THEME_COLOR
  }
}
