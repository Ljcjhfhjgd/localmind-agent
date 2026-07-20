/**
 * 文件名: src/stores/chat.js
 * 功能: 对话状态管理 + 请求队列 + 胸片报告 + Agent 步骤 + selectedDocs
 */
import { defineStore } from 'pinia'
import { chatApi } from '@/api'
import { useModeStore } from './mode'
import { ref, computed, watch } from 'vue'
const BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8765'

export const useChatStore = defineStore('chat', () => {
  const modeStore = useModeStore()
  const messages = ref([])
  const isStreaming = ref(false)
  const abortController = ref(null)
  const conversations = ref([])
  const loadingHistory = ref(false)

  const modeConvId = ref({})
  const modeMessages = ref({})
  const isNewConversation = ref(false)

  const xrayProgress = ref(null)
  const xrayResults = ref(null)
  const xrayReports = ref({})
  const xrayReportGenerating = ref(null)
  const xrayReportAbortController = ref(null)

  const agentSteps = ref([])

  const requestQueue = ref([])
  const isProcessing = ref(false)

  const memoryState = ref({
    active: false, type: '', status: '', result: '', collapsed: false,
  })

  const currentModeConvId = computed(() => modeConvId.value[modeStore.activeMode] || null)

  function getConvMessages(convId) {
    const mode = modeStore.activeMode
    if (!modeMessages.value[mode]) modeMessages.value[mode] = {}
    if (!modeMessages.value[mode][convId]) modeMessages.value[mode][convId] = []
    return modeMessages.value[mode][convId]
  }

  function syncToView(convMsgs) {
    messages.value = [...convMsgs]
  }

  async function createConversation(mode) {
    const modeKey = mode || modeStore.activeMode
    const currentId = modeConvId.value[modeKey]
    if (currentId && messages.value.length > 0) {
      if (!modeMessages.value[modeKey]) modeMessages.value[modeKey] = {}
      modeMessages.value[modeKey][currentId] = [...messages.value]
    }
    modeConvId.value[modeKey] = null
    messages.value = []
    xrayProgress.value = null
    xrayResults.value = null
    xrayReports.value = {}
    xrayReportGenerating.value = null
    if (xrayReportAbortController.value) {
      xrayReportAbortController.value.abort()
      xrayReportAbortController.value = null
    }
    agentSteps.value = []
    isNewConversation.value = true
    memoryState.value = { active: false, type: '', status: '', result: '', collapsed: false }
  }

  async function forceCreateConversation(mode) {
    const modeKey = mode || modeStore.activeMode
    modeConvId.value[modeKey] = null
    messages.value = []
    xrayProgress.value = null
    xrayResults.value = null
    xrayReports.value = {}
    xrayReportGenerating.value = null
    if (xrayReportAbortController.value) {
      xrayReportAbortController.value.abort()
      xrayReportAbortController.value = null
    }
    agentSteps.value = []
    isNewConversation.value = true
    memoryState.value = { active: false, type: '', status: '', result: '', collapsed: false }

    try {
      const res = await chatApi.createConversation(modeKey)
      modeConvId.value[modeKey] = res.conv_id
      isNewConversation.value = false
      await loadConversations(modeKey)
      return res.conv_id
    } catch (e) {
      console.error('强制创建对话失败:', e)
      return null
    }
  }

  async function switchConversation(convId) {
    const mode = modeStore.activeMode
    if (convId === modeConvId.value[mode] && messages.value.length > 0) {
      return
    }

    const currentId = modeConvId.value[mode]
    if (currentId && messages.value.length > 0) {
      if (!modeMessages.value[mode]) modeMessages.value[mode] = {}
      modeMessages.value[mode][currentId] = [...messages.value]
    }

    try {
      loadingHistory.value = true
      await chatApi.switchConversation(convId, mode)
      modeConvId.value[mode] = convId
      isNewConversation.value = false

      const cached = getConvMessages(convId)
      if (cached.length > 0) {
        messages.value = [...cached]
        restoreXrayFromMessages()
      } else {
        const history = await chatApi.getHistory(convId)
        const msgs = []
        for (const m of (history.history || [])) {
          // 如果有文件，提前 fetch Blob 以便 regenerate 使用
          let files = null
          if (m.files) {
            files = await Promise.all(m.files.map(async (f) => {
              const filePath = (f.path || '').replace(/\\/g, '/')
              const fileName = filePath.split('/').pop() || ''
              let blob = null
              if (fileName) {
                try {
                  const resp = await fetch(`${BASE}/files/uploads/${fileName}`)
                  if (resp.ok) blob = await resp.blob()
                } catch {}
              }
              return {
                name: f.name || '',
                type: f.type || '',
                url: fileName ? `${BASE}/files/uploads/${fileName}` : null,
                thumb: fileName ? `${BASE}/files/uploads/${fileName}` : null,
                path: f.path || '',
                file: blob,
              }
            }))
          }
          msgs.push({
            role: m.role,
            content: m.content,
            timestamp: m.timestamp || m.time,
            thinking: m.thinking || '',
            analyzeStatus: m.analyzeStatus || '',
            thinkCollapsed: true,
            suggestions: m.suggestions || [],
            isStreaming: false,
            xrayResult: m.xrayResult || null,
            xrayResults: m.xrayResults || null,
            xrayRejected: m.xrayRejected || null,
            xrayError: m.xrayError || null,
            agentSteps: m.agentSteps || [],
            multiAgentSteps: m.multiAgentSteps || [],
            searchResults: null,
            refs: null,
            stopped: m.stopped || false,
            accepted: false,
            files,
          })
        }
        if (!modeMessages.value[mode]) modeMessages.value[mode] = {}
        modeMessages.value[mode][convId] = msgs
        messages.value = [...msgs]
        restoreXrayFromMessages()
      }

      await loadConversations(mode)
    } catch (e) {
      console.error('切换对话失败:', e)
    } finally {
      loadingHistory.value = false
    }
  }

  function restoreXrayFromMessages() {
    xrayReports.value = {}
    xrayReportGenerating.value = null
    agentSteps.value = []
    for (const m of messages.value) {
      if (m.role === 'assistant' && m.agentSteps?.length) {
        for (const s of m.agentSteps) {
          const idx = agentSteps.value.findIndex(x => x.step === s.step)
          if (idx >= 0) {
            agentSteps.value[idx] = s
          } else {
            agentSteps.value.push(s)
          }
        }
      }
    }
    for (const m of [...messages.value].reverse()) {
      if (m.role === 'assistant' && m.xrayResults) {
        xrayResults.value = m.xrayResults
        for (const r of m.xrayResults) {
          if (r.report) xrayReports.value[r.file_name] = { content: r.report, loading: false }
        }
        return
      }
    }
    xrayResults.value = null
  }

  async function loadConversations(mode) {
    try {
      const res = await chatApi.getConversations(mode)
      conversations.value = res.conversations || []
    } catch (e) {
      console.error('加载对话列表失败:', e)
    }
  }

  async function restoreLastConversation(mode) {
    try {
      await loadConversations(mode)
      const convs = conversations.value
      if (convs.length === 0) return false
      const lastConv = convs[0]
      await switchConversation(lastConv.id)
      return true
    } catch (e) {
      console.error('恢复对话失败:', e)
      return false
    }
  }

  async function enqueueMessage(message, files = null, model = '', mode = null, displayContent = null, selectedDocs = null) {
    return new Promise((resolve) => {
      requestQueue.value.push({ message, files, model, mode, resolve, displayContent, selectedDocs })
      processQueue()
    })
  }

  async function processQueue() {
    if (isProcessing.value || requestQueue.value.length === 0) return
    isProcessing.value = true
    const { message, files, model, mode, resolve, displayContent, selectedDocs } = requestQueue.value.shift()
    if (mode && mode !== modeStore.activeMode) {
      beforeModeSwitch()
      modeStore.switchMode(mode)
      afterModeSwitch(mode)
    }
    try {
      await sendMessageInternal(message, files, false, model, false, displayContent, selectedDocs)
    } catch (e) {
      console.error('队列执行失败:', e.message)
    }
    isProcessing.value = false
    resolve()
    processQueue()
  }

  async function sendMessage(message, files = null, searchOn = false, model = '', isRegenerate = false, displayContent = null, selectedDocs = null) {
    if (isRegenerate) {
      return await sendMessageInternal(message, files, searchOn, model, true, displayContent, selectedDocs)
    }
    return await enqueueMessage(message, files, model, modeStore.activeMode, displayContent, selectedDocs)
  }

  async function sendMessageInternal(message, files = null, searchOn = false, model = '', isRegenerate = false, displayContent = null, selectedDocs = null) {
    if (isStreaming.value) { isStreaming.value = false }
    const mode = modeStore.activeMode
    let convId = modeConvId.value[mode]
    if (!convId) {
      try {
        const res = await chatApi.createConversation(mode)
        convId = res.conv_id
        modeConvId.value[mode] = convId
        isNewConversation.value = false
      } catch (e) {
        console.error('创建对话失败:', e)
        return
      }
    }
    if (!modeMessages.value[mode]) modeMessages.value[mode] = {}
    if (!modeMessages.value[mode][convId]) modeMessages.value[mode][convId] = []
    const convMsgs = modeMessages.value[mode][convId]
    if (!isRegenerate) {
      convMsgs.push({
        role: 'user', content: displayContent || message || '',
        timestamp: new Date().toISOString(), files: files || null,
      })
    }
    const aiMsg = {
      role: 'assistant', content: '', thinking: '', analyzeStatus: '',
      timestamp: new Date().toISOString(), isStreaming: true, suggestions: [],
      thinkCollapsed: true, stopped: false, accepted: false,
      xrayResult: null, xrayResults: null, xrayRejected: null, xrayError: null,
      agentSteps: [], multiAgentSteps: [], searchResults: null, refs: null, memoryState: null,
    }
    convMsgs.push(aiMsg)
    syncToView(convMsgs)
    isStreaming.value = true
    abortController.value = new AbortController()
    xrayProgress.value = null; xrayResults.value = null; xrayReports.value = {}; xrayReportGenerating.value = null; agentSteps.value = []
    let shouldDeleteConv = false
    try {
      await chatApi.sendMessage(message || '', files, searchOn, convId, {
        onChunk: (data) => {
          if (modeStore.activeMode !== mode) return
          if (data.content && typeof data.content === 'string') aiMsg.content += data.content
          if (data.think) {
            if (data.think.includes('正在分析') || data.think.includes('已分析') || data.think.includes('分析完成')) {
              aiMsg.analyzeStatus = data.think
            } else { aiMsg.thinking += data.think }
          }
          if (data.suggestions) aiMsg.suggestions = data.suggestions
          if (data.cancelled) aiMsg.stopped = true
          if (data.xray) aiMsg.xrayResult = data.xray
          if (data.xray_progress) xrayProgress.value = data.xray_progress
          if (data.xray_results) { aiMsg.xrayResults = data.xray_results; xrayResults.value = data.xray_results }
          if (data.xray_rejected) { aiMsg.xrayRejected = data.xray_rejected; aiMsg.isStreaming = false; isStreaming.value = false; shouldDeleteConv = true }
          if (data.xray_error) { aiMsg.xrayError = data.xray_error; aiMsg.isStreaming = false; isStreaming.value = false; shouldDeleteConv = true }
          if (data.agent_step) {
            const steps = [...(aiMsg.agentSteps || [])]
            const idx = steps.findIndex(s => s.step === data.agent_step.step)
            if (idx >= 0) { steps[idx] = data.agent_step } else { steps.push(data.agent_step) }
            aiMsg.agentSteps = steps; agentSteps.value = steps
          }
          if (data.type === 'multi_agent_step' && data.content) {
            const step = data.content
            const steps = [...(aiMsg.multiAgentSteps || [])]
            const idx = steps.findIndex(s => s.role === step.role && s.task === step.task)
            if (idx >= 0) {
              steps[idx] = { ...steps[idx], ...step }
            } else {
              steps.push(step)
            }
            aiMsg.multiAgentSteps = steps
          }
          if (data.search) aiMsg.searchResults = data.results
          if (data.refs) aiMsg.refs = data.refs
          if (data.title) loadConversations(mode)
          if (data.memory) { aiMsg.memoryState = { type: data.memory.type, status: data.memory.status, result: data.memory.result, collapsed: false } }
          syncToView(convMsgs)
        },
        onDone: () => {
          if (abortController.value?.signal.aborted) {
            aiMsg.stopped = true
            const fd = new FormData()
            fd.append('content', aiMsg.content || '')
            fd.append('stopped', '1')
            fetch(`${BASE}/chat/save_partial`, { method: 'POST', body: fd }).catch(() => {})
          }
          aiMsg.isStreaming = false
          isStreaming.value = false
          if (modeMessages.value[mode] && modeMessages.value[mode][convId]) {
            modeMessages.value[mode][convId] = [...convMsgs]
          }
          syncToView(convMsgs)
          if (shouldDeleteConv && convId) { cleanRejectedConversation(mode, convId) } else { loadConversations(mode) }
        },
        onError: (error) => { aiMsg.content = '错误: ' + error; aiMsg.isStreaming = false; isStreaming.value = false; syncToView(convMsgs); if (convId && messages.value.length <= 2) { cleanRejectedConversation(mode, convId) } },
        signal: abortController.value.signal,
      }, model, isRegenerate, selectedDocs)
    } catch (e) {
      if (e.name !== 'AbortError') {
        aiMsg.content = '请求失败: ' + e.message
      }
      aiMsg.isStreaming = false
      isStreaming.value = false
      syncToView(convMsgs)
    }
  }

  async function cleanRejectedConversation(mode, convId) {
    try {
      if (modeMessages.value[mode]) delete modeMessages.value[mode][convId]
      conversations.value = conversations.value.filter(c => c.id !== convId)
      if (modeConvId.value[mode] === convId) { modeConvId.value[mode] = null; messages.value = []; xrayResults.value = null; xrayProgress.value = null; xrayReports.value = {} }
      chatApi.deleteConversation(convId).catch(e => { console.warn('删除被拒绝的对话失败:', e.message) })
    } catch (e) { console.warn('清理对话失败:', e) }
  }

  async function generateXrayReport(fileName) {
    const convId = currentModeConvId.value; if (!convId) return
    if (xrayReportAbortController.value) { xrayReportAbortController.value.abort(); xrayReportAbortController.value = null }
    if (xrayReports.value[fileName]?.loading) return
    const existingContent = xrayReports.value[fileName]?.content || ''
    xrayReports.value[fileName] = { content: existingContent, loading: true }
    xrayReportGenerating.value = fileName
    const controller = new AbortController(); xrayReportAbortController.value = controller
    try {
      const response = await fetch(`${BASE}/chat/xray/report`, { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: new URLSearchParams({ conv_id: convId, file_name: fileName }), signal: controller.signal })
      const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = ''; let fullText = ''
      while (true) {
        const { done, value } = await reader.read(); if (done) break
        buffer += decoder.decode(value, { stream: true }); const lines = buffer.split('\n'); buffer = lines.pop() || ''
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue; const jsonStr = line.slice(6)
          if (jsonStr === '[DONE]') continue
          try { const data = JSON.parse(jsonStr); if (data.content) { fullText += data.content; xrayReports.value[fileName] = { content: fullText, loading: false } } else if (data.error) { xrayReports.value[fileName] = { content: fullText || ('报告生成失败: ' + data.error), loading: false } } } catch (e) {}
        }
      }
      if (xrayResults.value) { for (const r of xrayResults.value) { if (r.file_name === fileName) { r.report = fullText; break } } }
    } catch (e) { if (e.name === 'AbortError') return; console.error('生成报告失败:', e); if (!xrayReports.value[fileName]?.content) { xrayReports.value[fileName] = { content: '报告生成失败', loading: false } } }
    finally { if (xrayReports.value[fileName]) xrayReports.value[fileName].loading = false; xrayReportGenerating.value = null; xrayReportAbortController.value = null }
  }

  async function retrySingleXray(convId, fileName) {
    const mode = modeStore.activeMode
    try {
      const response = await fetch(`${BASE}/chat/xray/retry`, { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: new URLSearchParams({ conv_id: convId, file_name: fileName }) })
      const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = ''
      while (true) {
        const { done, value } = await reader.read(); if (done) break
        buffer += decoder.decode(value, { stream: true }); const lines = buffer.split('\n'); buffer = lines.pop() || ''
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue; const jsonStr = line.slice(6)
          if (jsonStr === '[DONE]') continue
          try {
            const data = JSON.parse(jsonStr)
            if (data.xray_retry_result) {
              if (xrayResults.value) { const idx = xrayResults.value.findIndex(r => r.file_name === fileName); if (idx !== -1) { xrayResults.value[idx] = data.xray_retry_result; xrayResults.value = [...xrayResults.value] } }
              for (const m of [...messages.value].reverse()) { if (m.role === 'assistant' && m.xrayResults) { const idx = m.xrayResults.findIndex(r => r.file_name === fileName); if (idx !== -1) { m.xrayResults[idx] = data.xray_retry_result; m.xrayResults = [...m.xrayResults] } break } }
              syncToView(modeMessages.value[mode][convId] || []); delete xrayReports.value[fileName]
            }
          } catch (e) {}
        }
      }
    } catch (e) { console.error('重新检测请求失败:', e) }
  }

  async function stopGeneration() {
    if (abortController.value) {
      abortController.value.abort()
      await chatApi.stopGeneration()
    }
    isStreaming.value = false
    isProcessing.value = false
    processQueue()
  }

  async function regenerate() {
    if (messages.value.length < 2) return
    const mode = modeStore.activeMode
    const convId = modeConvId.value[mode]; if (!convId) return
    const convMsgs = modeMessages.value[mode][convId]; if (!convMsgs) return
    const ai = convMsgs[convMsgs.length - 1]; if (ai.role !== 'assistant') return
    await chatApi.popLastMessage().catch(() => {})
    convMsgs.pop()
    const user = convMsgs[convMsgs.length - 1]; if (user.role !== 'user') return
    syncToView(convMsgs)
    let selectedDocs = null
    if (mode === 'rag') {
      try { const saved = localStorage.getItem('rag_selected_doc_names'); if (saved) { selectedDocs = JSON.parse(saved) } } catch {}
    }
    await sendMessage(user.content, user.files || null, false, '', true, null, selectedDocs)
  }

  async function clearConversation() {
    const mode = modeStore.activeMode; const convId = modeConvId.value[mode]
    if (convId) { await chatApi.clearHistory(); if (modeMessages.value[mode] && modeMessages.value[mode][convId]) { modeMessages.value[mode][convId] = [] } }
    messages.value = []; xrayResults.value = null; xrayProgress.value = null; xrayReports.value = {}; xrayReportGenerating.value = null
    if (xrayReportAbortController.value) { xrayReportAbortController.value.abort(); xrayReportAbortController.value = null }
    agentSteps.value = []; isNewConversation.value = true; isStreaming.value = false
    memoryState.value = { active: false, type: '', status: '', result: '', collapsed: false }
  }

  async function deleteConversation(convId) {
    const mode = modeStore.activeMode; const isCurrentConv = (modeConvId.value[mode] === convId)
    try {
      await chatApi.deleteConversation(convId); if (modeMessages.value[mode]) delete modeMessages.value[mode][convId]; await loadConversations(mode)
      if (isCurrentConv) {
        modeConvId.value[mode] = null; messages.value = []; xrayResults.value = null; xrayProgress.value = null; xrayReports.value = {}; xrayReportGenerating.value = null
        if (xrayReportAbortController.value) { xrayReportAbortController.value.abort(); xrayReportAbortController.value = null }
        agentSteps.value = []; isNewConversation.value = true; isStreaming.value = false
        memoryState.value = { active: false, type: '', status: '', result: '', collapsed: false }
      }
    } catch (e) { console.error('删除对话失败:', e) }
  }

  function beforeModeSwitch() {
    const mode = modeStore.activeMode; const convId = modeConvId.value[mode]
    if (convId && messages.value.length > 0) { if (!modeMessages.value[mode]) modeMessages.value[mode] = {}; modeMessages.value[mode][convId] = [...messages.value] }
  }

  function setupBeforeUnload() {
    const handler = () => {}
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }

  async function afterModeSwitch(newMode) {
    const VALID_CHAT_MODES = ['normal', 'agent', 'rag', 'xray', 'email']
    if (!VALID_CHAT_MODES.includes(newMode)) {
      messages.value = []
      conversations.value = []
      xrayResults.value = null
      xrayReports.value = {}
      xrayReportGenerating.value = null
      agentSteps.value = []
      isNewConversation.value = true
      isStreaming.value = false
      return
    }

    const convId = modeConvId.value[newMode]
    xrayProgress.value = null; xrayResults.value = null; xrayReports.value = {}; xrayReportGenerating.value = null
    if (xrayReportAbortController.value) { xrayReportAbortController.value.abort(); xrayReportAbortController.value = null }
    agentSteps.value = []
    if (convId && modeMessages.value[newMode] && modeMessages.value[newMode][convId]?.length > 0) { messages.value = [...modeMessages.value[newMode][convId]]; restoreXrayFromMessages(); isNewConversation.value = false }
    else if (convId) { await switchConversation(convId) }
    else { messages.value = []; isNewConversation.value = true }
    isStreaming.value = false; memoryState.value = { active: false, type: '', status: '', result: '', collapsed: false }; loadConversations(newMode)
  }

  return {
    messages, isStreaming, conversations, loadingHistory, currentModeConvId, memoryState,
    xrayProgress, xrayResults, xrayReports, xrayReportGenerating, xrayReportAbortController,
    agentSteps, requestQueue, isProcessing,
    createConversation, forceCreateConversation, switchConversation, loadConversations,
    restoreLastConversation, sendMessage, stopGeneration, regenerate,
    clearConversation, deleteConversation, beforeModeSwitch, afterModeSwitch,
    retrySingleXray, generateXrayReport, setupBeforeUnload,
  }
})