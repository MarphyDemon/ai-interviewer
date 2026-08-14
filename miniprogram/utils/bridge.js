class Bridge {
  constructor() {
    this.handlers = {}
    this.webViewContext = null
  }

  setWebViewContext(context) {
    this.webViewContext = context
  }

  handleMessages(messages) {
    if (!messages) return
    const msgs = Array.isArray(messages) ? messages : [messages]
    msgs.forEach(msg => {
      const { type, payload } = msg
      if (this.handlers[type]) {
        this.handlers[type](payload)
      }
    })
  }

  handleUrlParams(params) {
    if (params && params.action) {
      if (this.handlers[params.action]) {
        this.handlers[params.action](params)
      }
    }
  }

  sendToH5(type, payload) {
    if (!this.webViewContext) return
    const script = `window.__onMiniMessage(${JSON.stringify({ type, payload })})`
    this.webViewContext.evalJS(script)
  }

  on(type, handler) {
    this.handlers[type] = handler
  }
}

module.exports = new Bridge()