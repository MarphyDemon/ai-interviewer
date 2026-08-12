import { createI18n } from 'vue-i18n'
import en from './locales/en'
import zh from './locales/zh'

const stored = localStorage.getItem('lang')
const defaultLang = stored || 'en'

const i18n = createI18n({
  legacy: false,
  locale: defaultLang,
  fallbackLocale: 'en',
  messages: { en, zh },
})

export function setLanguage(lang: 'en' | 'zh') {
  i18n.global.locale.value = lang
  localStorage.setItem('lang', lang)
}

export function getLanguage(): 'en' | 'zh' {
  return i18n.global.locale.value as 'en' | 'zh'
}

export default i18n
