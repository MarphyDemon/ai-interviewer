import type { CapacitorConfig } from '@capacitor/cli'

const config: CapacitorConfig = {
  appId: 'com.aiinterviewer.app',
  appName: 'AI面试官',
  webDir: 'dist',
  server: {
    url: 'http://localhost:5173',
    cleartext: true,
  },
  plugins: {
    SplashScreen: {
      launchShowDuration: 2000,
      backgroundColor: '#1a1a2e',
      showSpinner: true,
      spinnerColor: '#4fc3f7',
    },
    StatusBar: {
      style: 'LIGHT',
      backgroundColor: '#1a1a2e',
      overlaysWebView: false,
    },
  },
}

export default config