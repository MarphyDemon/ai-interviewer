import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { loader as monacoLoader } from '@guolao/vue-monaco-editor'
import App from './App.vue'
import router from './router'
import i18n from './i18n'
import './style.css'

// Monaco Editor 通过本地静态资源加载（避免 Vite worker 打包配置，也不依赖 CDN）
monacoLoader.config({
  paths: { vs: '/vs' },
})

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(i18n)
app.mount('#app')
