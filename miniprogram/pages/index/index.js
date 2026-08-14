const bridge = require('../../utils/bridge.js')

Page({
  data: {
    webViewUrl: '',
    loaded: false,
    loading: true
  },

  onLoad(options) {
    bridge.handleUrlParams(options)
    
    const baseUrl = getApp().globalData.webViewUrl
    const params = options.action
      ? `?action=${options.action}&payload=${encodeURIComponent(JSON.stringify(options))}`
      : ''
    this.setData({ webViewUrl: baseUrl + params })
  },

  onWebViewLoad() {
    this.setData({ loaded: true, loading: false })
    wx.hideLoading()
    const webview = this.selectComponent('#webView')
    if (webview) {
      bridge.setWebViewContext(webview)
      bridge.sendToH5('ready', {})
    }
  },

  onWebViewError(e) {
    this.setData({ loading: false })
    wx.showToast({ title: '加载失败，请重试', icon: 'none' })
  },

  onMessage(e) {
    const data = e.detail.data
    if (Array.isArray(data)) {
      data.forEach(msg => bridge.handleMessages(msg))
    }
  },

  onShareAppMessage() {
    return {
      title: 'AI面试官',
      path: '/pages/index/index',
      imageUrl: '/images/share-cover.png'
    }
  },

  onShareTimeline() {
    return {
      title: 'AI面试官',
      imageUrl: '/images/share-cover.png'
    }
  }
})