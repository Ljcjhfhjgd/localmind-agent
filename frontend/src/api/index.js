/**
 * 文件名: src/api/index.js
 * 功能: 后端 API 封装（X-API-Key 由全局拦截自动注入）
 */
const BASE = import.meta.env.VITE_API_BASE || '/api'

export const chatApi = {
  async sendMessage(message, files, searchOn, convId, callbacks, model = '', isRegenerate = false, selectedDocs = null) {
    const fd = new FormData()
    fd.append('message', message)
    fd.append('search_on', searchOn ? '1' : '0')
    if (convId) fd.append('conv_id', convId)
    if (model) fd.append('model', model)
    if (isRegenerate) fd.append('skip_user', '1')
    if (selectedDocs && selectedDocs.length) {
      fd.append('selected_docs', JSON.stringify(selectedDocs))
    }
    if (files && files.length) {
      files.forEach((f) => {
        fd.append('files', f.file, f.name)
      })
    }
    const resp = await fetch(`${BASE}/chat`, {
      method: 'POST',
      body: fd,
      signal: callbacks?.signal,
    })
  
    if (resp.status === 403) {
      callbacks?.onError?.('API Key 不正确')
      return
    }
    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6).trim()
            if (data === '[DONE]') { callbacks?.onDone?.(); return }
            try { callbacks?.onChunk?.(JSON.parse(data)) } catch (e) {}
          }
        }
      }
    } catch (e) { if (e.name !== 'AbortError') callbacks?.onError?.(e.message) }
    callbacks?.onDone?.()
  },

  async stopGeneration() { await fetch(`${BASE}/chat/stop`, { method: 'POST' }) },
  async savePartial(content) { const fd = new FormData(); fd.append('content', content); await fetch(`${BASE}/chat/save_partial`, { method: 'POST', body: fd }) },
  async getHistory(convId) { const r = await fetch(`${BASE}/chat/history?conv_id=${convId}`); return r.json() },
  async clearHistory() { await fetch(`${BASE}/chat/history`, { method: 'DELETE' }) },
  async getConversations(mode) { const r = await fetch(`${BASE}/chat/conversations?mode=${mode || ''}`); return r.json() },
  async createConversation(mode = 'normal') { const fd = new FormData(); fd.append('mode', mode); const r = await fetch(`${BASE}/chat/conversations/new`, { method: 'POST', body: fd }); return r.json() },
  async switchConversation(convId, mode) { const fd = new FormData(); fd.append('conv_id', convId); fd.append('mode', mode); await fetch(`${BASE}/chat/conversations/switch`, { method: 'POST', body: fd }) },
  async deleteConversation(convId) { await fetch(`${BASE}/chat/conversations/${convId}`, { method: 'DELETE' }) },
  async saveConversation() { await fetch(`${BASE}/chat/conversations/save`, { method: 'POST' }) },
  async popLastMessage() { await fetch(`${BASE}/chat/conversations/pop`, { method: 'POST' }) },

  async getMemories() { const r = await fetch(`${BASE}/memory/list`); return r.json() },
  async deleteMemory(memoryId) { await fetch(`${BASE}/memory/${memoryId}`, { method: 'DELETE' }) },
  async clearMemories() { await fetch(`${BASE}/memory`, { method: 'DELETE' }) },
  async getMemorySettings() { const r = await fetch(`${BASE}/memory/settings`); return r.json() },
  async saveMemorySettings(enabled) { const fd = new FormData(); fd.append('enabled', enabled ? 'true' : 'false'); await fetch(`${BASE}/memory/settings`, { method: 'POST', body: fd }) },
}

export const knowledgeApi = {
  async getCollections() { const r = await fetch(`${BASE}/rag/collections`); return r.json() },
  async uploadDocument(file) { const fd = new FormData(); fd.append('file', file); await fetch(`${BASE}/rag/upload`, { method: 'POST', body: fd }) },
}