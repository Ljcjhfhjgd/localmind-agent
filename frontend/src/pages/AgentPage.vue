<!--
文件名: src/pages/AgentPage.vue
功能: Agent 模式 - 对话/步骤条 双视图 + 右侧时间线 + 多Agent协作 + 文件上传
-->
<template>
  <div class="agent-page">
    <div class="agent-topbar">
      <div class="agent-info">
        <Bot :size="16" />
        <span>Agent 模式</span>
      </div>
      <div class="view-tabs">
        <button :class="{ active: view === 'chat' }" @click="view = 'chat'">
          <MessageCircle :size="14" /> 对话
        </button>
        <button :class="{ active: view === 'steps' }" @click="view = 'steps'">
          <GitBranch :size="14" /> 步骤条
        </button>
      </div>
    </div>

    <div class="agent-body" ref="bodyRef">
      <div class="agent-main">
        <div v-if="!chatStore.messages.length" class="agent-empty">
          <Bot :size="40" color="#0071e3" />
          <h2>Agent 模式</h2>
          <p>复杂问题自动搜索、计算、翻译、查天气</p>
          <div v-if="!promptsReady" class="prompts-loading"><span></span><span></span><span></span></div>
          <div v-else class="empty-prompts"><button v-for="q in prompts" :key="q" class="prompt-chip" @click="send(q)">{{ q }}</button></div>
          <button v-if="promptsReady" class="refresh-btn" @click="refreshPrompts">换一批</button>
        </div>

        <div v-if="view === 'chat' && chatStore.messages.length" class="view-chat-wrap">
          <div class="view-chat" ref="chatRef">
            <div v-for="(m, i) in chatStore.messages" :key="i" :class="['msg', m.role]" :ref="el => setMsgRef(i, el)">
              <template v-if="m.role === 'user'">
                <div v-if="m.files && m.files.length" class="attach-card">
                  <div v-if="m.files.some(f => f && (f.type === 'image' || f.name?.match(/\.(jpg|jpeg|png|gif|bmp|webp|svg)$/i)))" class="attach-images">
                    <div v-for="(f, fi) in m.files.filter(f => f && (f.type === 'image' || f.name?.match(/\.(jpg|jpeg|png|gif|bmp|webp|svg)$/i)))" :key="'img-'+fi" class="attach-image-item">
                      <img v-if="f.thumb || f.url" :src="f.thumb || f.url" :alt="f.name" />
                      <Image v-else :size="32" />
                      <span class="attach-image-label">{{ f.name }}</span>
                    </div>
                  </div>
                  <div v-if="m.files.some(f => f && !(f.type === 'image' || f.name?.match(/\.(jpg|jpeg|png|gif|bmp|webp|svg)$/i)))" class="attach-files">
                    <div v-for="(f, fi) in m.files.filter(f => f && !(f.type === 'image' || f.name?.match(/\.(jpg|jpeg|png|gif|bmp|webp|svg)$/i)))" :key="'file-'+fi" class="attach-file-row"><FileText :size="14" /><span class="attach-file-name">{{ f.name }}</span></div>
                  </div>
                </div>
                <div class="bubble user">{{ m.content }}</div>
              </template>
              <div v-else class="assistant-block">
                <div v-if="m.analyzeStatus" class="analyze-inline">
                  <span class="ai-icon" style="color: #34c759;">
                    <Image v-if="m.analyzeStatus.includes('图片')" :size="12" />
                    <FileText v-else :size="12" />
                  </span>
                  <span class="ai-label">分析</span>
                  <span class="ai-task">{{ m.analyzeStatus }}</span>
                  <span class="ai-status-icon">
                    <Loader v-if="!isAnalyzeDone(m.analyzeStatus)" :size="12" color="#f59e0b" />
                    <CheckCircle v-else :size="12" color="#34c759" />
                  </span>
                </div>
                <div v-if="m.multiAgentSteps?.length" class="multi-agent-inlines">
                  <div v-for="step in m.multiAgentSteps" :key="step.role + '|' + step.task" class="multi-agent-inline">
                    <span class="ma-icon" :style="{ color: agentColor(step.role) }">
                      <component :is="agentIcon(step.role)" :size="12" />
                    </span>
                    <span class="ma-label">{{ agentLabel(step.role) }}</span>
                    <span class="ma-task">{{ step.task }}</span>
                    <span class="ma-status-icon">
                      <Loader v-if="isStepRunning(step)" :size="12" color="#f59e0b" />
                      <CheckCircle v-else-if="step.status === 'ok'" :size="12" color="#34c759" />
                      <XCircle v-else-if="step.status === 'error'" :size="12" color="#ff3b30" />
                    </span>
                  </div>
                </div>
                <div v-if="m.content" :class="['bubble', 'assistant', { stopped: m.stopped }]">
                  <template v-for="(part, pi) in parseContent(m.content)" :key="pi"><CodeBlock v-if="part.type === 'code'" :lang="part.lang" :code="part.code" /><div v-else class="content" v-html="part.html"></div></template>
                </div>
                <div v-if="m.stopped" class="stopped-bar">
                  <AlertCircle :size="14" /> 已停止生成
                  <button v-if="i === chatStore.messages.length - 1" class="regenerate-btn" @click="chatStore.regenerate()"><RefreshCw :size="13" /> 重新生成</button>
                </div>
                <div v-if="m.isStreaming && !m.content && !m.multiAgentSteps?.length && !m.analyzeStatus" class="typing"><span></span><span></span><span></span></div>
                <div v-if="!m.isStreaming && m.content" class="actions">
                  <button @click="copy(m.content)"><Copy :size="13" /> 复制</button>
                  <button v-if="i === chatStore.messages.length - 1" @click="chatStore.regenerate()"><RefreshCw :size="13" /> 重新生成</button>
                  <span class="time">{{ fmt(m.timestamp) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="view === 'steps' && chatStore.messages.length" class="view-steps-wrap">
          <div class="view-steps">
            <div v-if="!currentRoundSteps.length && !currentQuestion" class="steps-empty"><Clock :size="32" color="#b0b0b5" /><p>暂无步骤</p></div>
            <div class="timeline-steps" v-else>
              <div class="timeline-item" v-if="currentQuestion">
                <div class="timeline-line-wrap">
                  <div class="timeline-dot question-dot"><MessageCircle :size="16" color="#fff" /></div>
                  <div class="timeline-line"></div>
                </div>
                <div class="timeline-card question-card">
                  <div class="timeline-card-head">
                    <span class="step-tag question-tag"><MessageCircle :size="12" /> 用户提问</span>
                  </div>
                  <div class="timeline-question">{{ currentQuestion }}</div>
                </div>
              </div>

              <div v-for="(step, si) in currentRoundSteps" :key="step.role + '|' + step.task" class="timeline-item">
                <div class="timeline-line-wrap">
                  <div class="timeline-dot" :style="{ background: step.status === 'ok' ? agentColor(step.role) : step.status === 'error' ? '#ff3b30' : isStepRunning(step) ? '#f59e0b' : '#d1d1d6' }">
                    <Loader v-if="isStepRunning(step)" :size="16" color="#fff" />
                    <component v-else :is="agentIcon(step.role)" :size="16" color="#fff" />
                  </div>
                  <div v-if="si < currentRoundSteps.length - 1" class="timeline-line"></div>
                </div>
                <div class="timeline-card" :class="{ 'card-ok': step.status === 'ok', 'card-error': step.status === 'error', 'card-running': isStepRunning(step) }">
                  <div class="timeline-card-head" @click="toggleStep(si)">
                    <span class="step-tag ma-tag" :style="{ background: agentBg(step.role), color: agentColor(step.role) }">
                      <component :is="agentIcon(step.role)" :size="12" /> {{ agentLabel(step.role) }}
                    </span>
                    <span class="step-status-text">
                      <Loader v-if="isStepRunning(step)" :size="12" color="#f59e0b" />
                      <span v-else-if="step.status === 'ok'" style="color: #34c759;">完成</span>
                      <span v-else-if="step.status === 'error'" style="color: #ff3b30;">失败</span>
                      <span v-else style="color: #b0b0b5;">等待</span>
                    </span>
                    <span class="step-expand"><ChevronDown v-if="!expandedSteps[si]" :size="14" /><ChevronUp v-else :size="14" /></span>
                  </div>
                  <div class="timeline-thought">{{ step.task }}</div>
                  <div v-if="expandedSteps[si]" class="timeline-expand">
                    <div v-if="step.keywords" class="timeline-keywords"><span class="ma-detail-label">🔑 关键词</span> {{ step.keywords }}</div>
                    <div v-if="step.city" class="timeline-keywords"><span class="ma-detail-label">📍 城市</span> {{ step.city }}</div>
                    <div v-if="step.target" class="timeline-keywords"><span class="ma-detail-label">🌐 目标语言</span> {{ step.target }}</div>
                    <div v-if="step.code" class="timeline-obs-full">
                      <div class="timeline-obs-label"><Terminal :size="13" color="#6366f1" /> 代码</div>
                      <div class="timeline-obs-content"><pre>{{ step.code }}</pre></div>
                    </div>
                    <div v-if="step.role === 'planner' && step.result" class="timeline-obs-full">
                      <div class="timeline-obs-label"><ListOrdered :size="13" color="#86868b" /> 任务列表</div>
                      <div class="timeline-obs-content">
                        <ol class="plan-list">
                          <li v-for="(item, idx) in parsePlanList(step.result)" :key="idx">
                            <span class="plan-role">{{ agentLabel(item.role) }}</span>
                            <span class="plan-task">{{ item.task }}</span>
                          </li>
                        </ol>
                      </div>
                    </div>
                    <div v-else-if="step.result && step.role === 'analyzer'" class="timeline-obs-full">
                      <div class="timeline-obs-label"><Eye :size="13" color="#34c759" /> 分析详情</div>
                      <div class="timeline-obs-content">{{ step.result }}</div>
                    </div>
                    <div v-else-if="step.result && step.role !== 'planner'" class="timeline-obs-full">
                      <div class="timeline-obs-label"><Eye :size="13" color="#34c759" /> 完整结果</div>
                      <div class="timeline-obs-content">{{ step.result }}</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="rounds.length > 0" class="timeline-fixed"><div class="timeline-line"></div><div class="timeline-scroll"><div v-for="(r, ri) in rounds" :key="ri" class="timeline-node" :class="{ active: selectedRound === ri }" @click="scrollToRound(ri)" @mouseenter="showTooltip(ri)" @mouseleave="hideTooltip"><div class="timeline-dot"></div><transition name="tooltip-fade"><div v-if="tooltip.visible && tooltip.index === ri" class="timeline-tooltip"><div class="tooltip-content">{{ r.label }}</div></div></transition></div></div></div>
    </div>

    <div class="input-area" @dragover.prevent="dragOver = true" @dragleave.prevent="dragOver = false" @drop.prevent="onDrop" :class="{ 'drag-over': dragOver }">
      <div v-if="uploadFiles.length" class="upload-preview-area">
        <div class="upload-images"><div v-for="(f, i) in imageFiles" :key="'up-img-'+i" class="upload-image-item"><img :src="f.thumb" :alt="f.name" /><button class="upload-remove-btn" @click="removeUploadFile(f.id)"><X :size="12" /></button><span class="upload-file-name">{{ f.name }}</span></div></div>
        <div class="upload-files"><div v-for="(f, i) in docFiles" :key="'up-doc-'+i" class="upload-file-item"><FileText :size="16" /><span>{{ f.name }}</span><button class="upload-remove-btn" @click="removeUploadFile(f.id)"><X :size="12" /></button></div></div>
      </div>
      <div class="input-row">
        <button class="input-btn" @click="$refs.fi.click()"><Paperclip :size="18" /></button>
        <input ref="fi" type="file" hidden multiple @change="onFileSelect" accept="image/*,.pdf,.doc,.docx,.txt,.csv,.xlsx,.xls,.py,.js,.json" />
        <textarea ref="ta" v-model="txt" class="input-field" placeholder="输入复杂问题，或拖拽文件..." rows="1" @input="resize" @keydown.enter.exact.prevent="sendMsg" @paste="onPaste"></textarea>
        <button v-if="chatStore.isStreaming" class="send-btn stop" @click="chatStore.stopGeneration()"><Square :size="14" /></button>
        <button v-else class="send-btn" :class="{ active: txt.trim() || uploadFiles.length }" :disabled="!txt.trim() && !uploadFiles.length" @click="sendMsg"><Send :size="16" /></button>
      </div>
      <div class="input-hint">Agent 模式 · 自动搜索、计算、翻译、查天气、总结网页<span v-if="uploadFiles.length"> · 已选 {{ uploadFiles.length }} 个文件</span></div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, reactive, onMounted } from 'vue'
import { Bot, Eye, MessageCircle, GitBranch, Copy, Send, Square, Loader, Zap, Clock, Search, Languages, CloudSun, Terminal, Calculator, ChevronDown, ChevronUp, RefreshCw, AlertCircle, CheckCircle, XCircle, FileText, ListOrdered, Paperclip, X, Image } from 'lucide-vue-next'
import { useChatStore } from '@/stores/chat'
import CodeBlock from '@/components/CodeBlock.vue'

const chatStore = useChatStore()
const chatRef = ref(null)
const bodyRef = ref(null)
const ta = ref(null)
const txt = ref('')
const view = ref('chat')
const selectedRound = ref(null)
const msgRefs = {}
const BATCH_SIZE = 4
let sendLock = false
const allQuestions = ref([])
const prompts = ref([])
const promptsReady = ref(false)
const expandedSteps = reactive({})
function toggleStep(index) { expandedSteps[index] = !expandedSteps[index] }

// ===== 文件上传相关 =====
const MAX_FILES = 6
const MAX_IMAGE_SIZE = 10 * 1024 * 1024
const uploadFiles = ref([])
const dragOver = ref(false)
let fileIdCounter = 0
const imageFiles = computed(() => uploadFiles.value.filter(f => f.type === 'image'))
const docFiles = computed(() => uploadFiles.value.filter(f => f.type !== 'image'))

function getFileType(f) {
  const e = f.name.split('.').pop()?.toLowerCase() || ''
  return ['jpg','jpeg','png','gif','bmp','webp','svg'].includes(e) ? 'image' : 'file'
}

function createThumbnail(f) {
  return new Promise(r => {
    if (getFileType(f) !== 'image') { r(null); return }
    const rd = new FileReader()
    rd.onload = e => {
      const img = new window.Image()
      img.onload = () => {
        const c = document.createElement('canvas')
        const mw = 120, mh = 120
        let w = img.width, h = img.height
        if (w > h) { if (w > mw) { h *= mw / w; w = mw } }
        else { if (h > mh) { w *= mh / h; h = mh } }
        c.width = w; c.height = h
        c.getContext('2d').drawImage(img, 0, 0, w, h)
        r(c.toDataURL('image/jpeg', 0.7))
      }
      img.src = e.target.result
    }
    rd.readAsDataURL(f)
  })
}

async function addFiles(fl) {
  for (const f of fl) {
    if (uploadFiles.value.length >= MAX_FILES) break
    if (f.size > MAX_IMAGE_SIZE && getFileType(f) === 'image') continue
    const t = getFileType(f)
    const id = ++fileIdCounter
    uploadFiles.value.push({
      id, file: f, name: f.name, type: t,
      url: t === 'image' ? URL.createObjectURL(f) : null,
      thumb: t === 'image' ? await createThumbnail(f) : null
    })
  }
}

function removeUploadFile(id) {
  const i = uploadFiles.value.findIndex(f => f.id === id)
  if (i !== -1) {
    const f = uploadFiles.value[i]
    if (f.url) URL.revokeObjectURL(f.url)
    uploadFiles.value.splice(i, 1)
  }
}

function onFileSelect(e) {
  if (e.target.files.length) addFiles(e.target.files)
  e.target.value = ''
}

function onDrop(e) {
  dragOver.value = false
  if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files)
}

function onPaste(e) {
  const items = e.clipboardData?.items
  if (!items) return
  const imageFiles = []
  for (const item of items) {
    if (item.type.startsWith('image/')) {
      const file = item.getAsFile()
      if (file) imageFiles.push(file)
    }
  }
  if (imageFiles.length) {
    e.preventDefault()
    addFiles(imageFiles)
  }
}
// ===== 文件上传相关结束 =====

function shuffleArray(arr) { const a = [...arr]; for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1));[a[i], a[j]] = [a[j], a[i]] } return a }
function refreshPrompts() { const source = allQuestions.value.length ? allQuestions.value : ['帮我算一下 1+2+...+100 的和','搜索一下最新 AI 新闻','今天北京什么天气','把"你好世界"翻译成日语','用 Python 生成斐波那契数列前 20 项']; prompts.value = shuffleArray(source).slice(0, BATCH_SIZE) }
async function loadPrompts() { try { const res = await fetch('/src/data/agent_questions.json'); if (res.ok) { const data = await res.json(); if (data.length) allQuestions.value = data } } catch (e) {} refreshPrompts(); promptsReady.value = true }
function setMsgRef(i, el) { if (el) msgRefs[i] = el }

const rounds = computed(() => { const r = []; let ri = 0; for (let i = 0; i < chatStore.messages.length; i++) { if (chatStore.messages[i].role === 'user') { r.push({ index: ri, label: chatStore.messages[i].content || '(空)', msgIndex: i }); ri++ } } return r })
function scrollToRound(ri) { selectedRound.value = ri; const r = rounds.value[ri]; if (!r) return; nextTick(() => { const el = msgRefs[r.msgIndex]; if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' }) }) }

const currentQuestion = computed(() => {
  const ri = selectedRound.value !== null ? selectedRound.value : rounds.value.length - 1
  const r = rounds.value[ri]
  return r ? r.label : ''
})

const currentRoundSteps = computed(() => {
  const ri = selectedRound.value !== null ? selectedRound.value : rounds.value.length - 1
  const r = rounds.value[ri]
  if (!r) return []
  for (let i = r.msgIndex + 1; i < chatStore.messages.length; i++) {
    const m = chatStore.messages[i]
    if (m.role === 'assistant' && m.multiAgentSteps?.length) return m.multiAgentSteps
    if (m.role === 'user') break
  }
  return []
})

const tooltip = reactive({ visible: false, index: -1 })
let hideTimer = null
function showTooltip(ri) { clearTimeout(hideTimer); tooltip.index = ri; tooltip.visible = true }
function hideTooltip() { hideTimer = setTimeout(() => { tooltip.visible = false }, 150) }

function isAnalyzeDone(t) { return t?.includes('分析完成') || t?.includes('已分析') }

function isStepRunning(step) {
  return step.status === 'running' || step.status === 'planning' || step.status === 'summarizing'
}

function agentIcon(role) {
  const icons = { search: Search, code: Terminal, review: Eye, weather: CloudSun, translate: Languages, time: Clock, calculate: Calculator, planner: Bot, summarizer: FileText, analyzer: Image }
  return icons[role] || Zap
}
function agentBg(role) {
  const bgs = { search: 'rgba(0,113,227,0.08)', code: 'rgba(99,102,241,0.08)', review: 'rgba(52,199,89,0.08)', weather: 'rgba(245,158,11,0.08)', translate: 'rgba(139,92,246,0.08)', time: 'rgba(6,182,212,0.08)', calculate: 'rgba(236,72,153,0.08)', planner: 'rgba(134,134,139,0.08)', summarizer: 'rgba(255,149,0,0.08)', analyzer: 'rgba(52,199,89,0.08)' }
  return bgs[role] || 'rgba(107,114,128,0.08)'
}
function agentColor(role) {
  const colors = { search: '#0071e3', code: '#6366f1', review: '#34c759', weather: '#f59e0b', translate: '#8b5cf6', time: '#06b6d4', calculate: '#ec4899', planner: '#86868b', summarizer: '#ff9500', analyzer: '#34c759' }
  return colors[role] || '#6b7280'
}
function agentLabel(role) {
  const labels = { search: '搜索', code: '代码', review: '审查', weather: '天气', translate: '翻译', time: '时间', calculate: '计算', planner: '规划', summarizer: '汇总', analyzer: '分析' }
  return labels[role] || role
}

function parsePlanList(result) {
  try {
    const plan = JSON.parse(result)
    if (Array.isArray(plan)) return plan
    return []
  } catch (e) {
    return []
  }
}

function parseContent(c) { if (!c) return [{ type:'text', html:'' }]; c = c.replace(/```(\w+)([^\n`])/g,'```$1\n$2'); const p = []; const re = /```\s*(\w*)\s*\n([\s\S]*?)```/g; let last = 0, m; while ((m = re.exec(c)) !== null) { if (m.index > last) p.push({ type:'text', html: md(c.slice(last, m.index)) }); p.push({ type:'code', lang: m[1]||'', code: m[2].trim() }); last = m.index + m[0].length } if (last < c.length) p.push({ type:'text', html: md(c.slice(last)) }); if (!p.length) p.push({ type:'text', html: md(c) }); return p }
function md(c) { if (!c) return ''; c = c.replace(/```/g,''); c = c.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>'); c = c.replace(/\n/g,'<br>'); return c }

function fmt(t) {
  if (!t) return ''
  const d = new Date(t), now = new Date(), diff = now - d
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
  if (d.toDateString() === now.toDateString()) return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
function copy(t) { const d = document.createElement('div'); d.innerHTML = t; navigator.clipboard.writeText(d.textContent || '').catch(() => {}) }
function resize() { const el = ta.value; if (el) { el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, 100) + 'px' } }

async function sendMsg() {
  if (sendLock) return
  const m = txt.value.trim()
  if (!m && !uploadFiles.value.length) return
  if (chatStore.isStreaming) return
  sendLock = true; setTimeout(() => { sendLock = false }, 500)
  selectedRound.value = null
  const fp = uploadFiles.value.map(f => ({ name: f.name, type: f.type, file: f.file, thumb: f.thumb, url: f.url }))
  chatStore.sendMessage(m, fp.length ? fp : null, false, 'agent')
  txt.value = ''
  uploadFiles.value = []
  nextTick(() => { if (ta.value) ta.value.style.height = 'auto' })
}

function send(m) { if (sendLock) return; if (chatStore.isStreaming) return; sendLock = true; setTimeout(() => { sendLock = false }, 500); selectedRound.value = null; chatStore.sendMessage(m, null, false, 'agent') }

function scrollBottom() { const el = bodyRef.value; if (el) nextTick(() => el.scrollTo({ top: el.scrollHeight, behavior: 'instant' })) }
function isNearBottom() { const el = bodyRef.value; if (!el) return true; return el.scrollHeight - el.scrollTop - el.clientHeight < 60 }

watch(() => chatStore.messages.length, () => { nextTick(() => scrollBottom()) }, { immediate: true })
watch(() => chatStore.messages[chatStore.messages.length - 1]?.content, () => { if (chatStore.isStreaming && isNearBottom()) scrollBottom() })

onMounted(() => { loadPrompts() })
</script>

<style scoped>
.agent-page { display: flex; flex-direction: column; height: 100%; background: #fff; }
.agent-topbar { display: flex; align-items: center; justify-content: space-between; padding: 8px 16px; background: #f5f5f7; border-bottom: 1px solid rgba(0,0,0,0.06); flex-shrink: 0; }
.agent-info { display: flex; align-items: center; gap: 6px; font-size: 13px; color: #1d1d1f; }
.view-tabs { display: flex; gap: 2px; }
.view-tabs button { display: flex; align-items: center; gap: 4px; padding: 5px 12px; border: none; border-radius: 6px; background: transparent; color: #86868b; cursor: pointer; font-size: 12px; font-family: inherit; }
.view-tabs button:hover { background: rgba(0,0,0,0.04); }
.view-tabs button.active { background: rgba(0,113,227,0.1); color: #0071e3; }
.agent-body { flex: 1; display: flex; overflow-y: auto; overflow-x: hidden; position: relative; padding-right: 44px; }
.agent-body::-webkit-scrollbar { width: 4px; }
.agent-body::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.1); border-radius: 2px; }
.agent-main { flex: 1; display: flex; flex-direction: column; min-height: 0; min-height: min-content; }
.agent-empty { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; }
.agent-empty h2 { font-size: 18px; font-weight: 600; color: #1d1d1f; }
.agent-empty p { font-size: 14px; color: #86868b; }
.prompts-loading { display: flex; gap: 6px; padding: 12px 0; }
.prompts-loading span { width: 6px; height: 6px; background: #0071e3; border-radius: 50%; opacity: 0.5; animation: bounce 1.2s infinite; }
.prompts-loading span:nth-child(2) { animation-delay: 0.2s; }
.prompts-loading span:nth-child(3) { animation-delay: 0.4s; }
.empty-prompts { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; justify-content: center; max-width: 520px; }
.prompt-chip { padding: 8px 16px; border: 1px solid rgba(0,0,0,0.08); border-radius: 12px; background: #fff; color: #1d1d1f; cursor: pointer; font-size: 13px; font-family: inherit; transition: all 0.15s; }
.prompt-chip:hover { border-color: #0071e3; color: #0071e3; background: rgba(0,113,227,0.04); }
.refresh-btn { padding: 6px 16px; border-radius: 14px; border: 1px solid rgba(0,0,0,0.08); background: transparent; color: #86868b; cursor: pointer; font-size: 12px; font-family: inherit; margin-top: 14px; transition: all 0.15s; }
.refresh-btn:hover { border-color: #0071e3; color: #0071e3; background: rgba(0,113,227,0.04); }
.view-chat-wrap { flex: 1; display: flex; justify-content: center; }
.view-chat { height: auto; min-height: 100%; overflow: visible; padding: 20px 24px; max-width: 780px; width: 100%; }
.msg { margin-bottom: 16px; }
.msg.user { display: flex; flex-direction: column; align-items: flex-end; }
.bubble { padding: 12px 16px; border-radius: 18px; font-size: 15px; line-height: 1.6; word-break: break-word; max-width: 80%; }
.bubble.user { background: #0071e3; color: #fff; border-bottom-right-radius: 4px; }
.bubble.assistant { background: #fff; color: #1d1d1f; border: 1px solid rgba(0,0,0,0.06); border-bottom-left-radius: 4px; }
.bubble.assistant.stopped { border-color: rgba(255,149,0,0.25); }
.attach-card { background: #f0f0f3; border-radius: 16px; padding: 10px; margin-bottom: 6px; max-width: 100%; }
.attach-images { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 6px; }
.attach-images:last-child { margin-bottom: 0; }
.attach-image-item { cursor: pointer; flex-shrink: 0; }
.attach-image-item img { width: 64px; height: 64px; object-fit: cover; border-radius: 8px; display: block; }
.attach-image-label { display: block; font-size: 10px; color: #86868b; text-align: center; margin-top: 2px; max-width: 64px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.attach-files { display: flex; flex-direction: column; gap: 3px; }
.attach-file-row { display: flex; align-items: center; gap: 6px; padding: 5px 8px; background: rgba(0,0,0,0.03); border-radius: 6px; color: #86868b; }
.attach-file-name { font-size: 12px; color: #1d1d1f; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.analyze-inline {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; color: #86868b; margin-bottom: 6px;
}
.ai-icon { display: flex; align-items: center; flex-shrink: 0; }
.ai-label { font-weight: 500; color: #1d1d1f; min-width: 28px; }
.ai-task { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.ai-status-icon { flex-shrink: 0; display: flex; align-items: center; }
.multi-agent-inlines { display: flex; flex-direction: column; gap: 2px; margin-bottom: 8px; }
.multi-agent-inline { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #86868b; }
.ma-icon { display: flex; align-items: center; flex-shrink: 0; }
.ma-label { font-weight: 500; color: #1d1d1f; min-width: 32px; }
.ma-task { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.ma-status-icon { flex-shrink: 0; display: flex; align-items: center; }
.typing { display: flex; gap: 4px; }
.typing span { width: 6px; height: 6px; background: #0071e3; border-radius: 50%; animation: bounce 1.2s infinite; opacity: 0.5; }
.typing span:nth-child(2) { animation-delay: 0.2s; }
.typing span:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-4px)} }
.actions { display: flex; align-items: center; gap: 8px; margin-top: 4px; opacity: 0; transition: opacity 0.2s; }
.assistant-block:hover .actions { opacity: 1; }
.actions button { display: flex; align-items: center; gap: 3px; padding: 3px 10px; border: 1px solid rgba(0,0,0,0.08); border-radius: 10px; background: #fff; color: #86868b; cursor: pointer; font-size: 12px; }
.actions button:hover { border-color: #0071e3; color: #0071e3; }
.time { font-size: 11px; color: #b0b0b5; margin-left: auto; }
.stopped-bar { display: flex; align-items: center; gap: 8px; margin-top: 8px; padding: 10px 14px; background: #fff3cd; border: 1px solid rgba(255,149,0,0.2); border-radius: 10px; font-size: 13px; color: #856404; font-weight: 500; }
.stopped-bar .regenerate-btn { display: inline-flex; align-items: center; gap: 4px; padding: 5px 14px; border: 1px solid #0071e3; border-radius: 8px; background: #ffffff; color: #0071e3; cursor: pointer; font-size: 12px; font-family: inherit; font-weight: 500; margin-left: auto; }
.stopped-bar .regenerate-btn:hover { background: #0071e3; color: #ffffff; }
.view-steps-wrap { flex: 1; display: flex; justify-content: center; }
.view-steps { height: auto; min-height: 100%; overflow: visible; padding: 24px; max-width: 780px; width: 100%; }
.steps-empty { text-align: center; color: #b0b0b5; padding: 60px 20px; display: flex; flex-direction: column; align-items: center; gap: 10px; }
.timeline-steps { display: flex; flex-direction: column; }
.timeline-item { display: flex; gap: 0; }
.timeline-line-wrap { display: flex; flex-direction: column; align-items: center; width: 40px; flex-shrink: 0; }
.timeline-dot { width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; }
.question-dot { background: #86868b; }
.timeline-line { width: 2px; flex: 1; min-height: 20px; background: rgba(0,0,0,0.08); }
.timeline-card { flex: 1; margin-left: 12px; margin-bottom: 20px; background: #fff; border: 1px solid rgba(0,0,0,0.06); border-radius: 14px; padding: 16px; min-width: 0; transition: border-color 0.2s; }
.timeline-card.card-ok { border-color: rgba(52,199,89,0.2); }
.timeline-card.card-error { border-color: rgba(255,59,48,0.2); }
.timeline-card.card-running { border-color: rgba(245,158,11,0.2); }
.question-card { background: #f9f9fb; }
.timeline-card-head { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; cursor: pointer; user-select: none; }
.step-tag { display: inline-flex; align-items: center; gap: 3px; padding: 3px 10px; border-radius: 8px; font-size: 11px; font-weight: 500; }
.question-tag { background: rgba(0,0,0,0.05); color: #86868b; }
.ma-tag { font-size: 11px; }
.step-status-text { display: inline-flex; align-items: center; gap: 4px; font-size: 11px; margin-left: auto; }
.step-expand { color: #b0b0b5; cursor: pointer; display: flex; align-items: center; }
.timeline-thought { font-size: 13px; color: #8b5cf6; margin-bottom: 8px; line-height: 1.5; }
.timeline-keywords { font-size: 12px; color: #86868b; margin-bottom: 6px; }
.ma-detail-label { font-weight: 500; color: #1d1d1f; }
.timeline-expand { margin-top: 8px; }
.timeline-obs-full { margin-top: 4px; }
.timeline-obs-label { display: flex; align-items: center; gap: 4px; font-size: 12px; color: #34c759; margin-bottom: 4px; }
.timeline-obs-content { font-size: 12px; color: #1d1d1f; line-height: 1.6; white-space: pre-wrap; word-break: break-word; max-height: 400px; overflow-y: auto; background: #f9f9fb; border-radius: 8px; padding: 10px; }
.timeline-question { font-size: 14px; color: #1d1d1f; line-height: 1.5; }
.plan-list { margin: 0; padding-left: 20px; }
.plan-list li { margin-bottom: 6px; font-size: 13px; line-height: 1.5; }
.plan-role { display: inline-block; padding: 1px 8px; border-radius: 6px; font-size: 11px; font-weight: 500; margin-right: 8px; background: rgba(0,113,227,0.08); color: #0071e3; }
.plan-task { color: #1d1d1f; }
.timeline-fixed { position: fixed; top: 96px; right: 0; width: 40px; height: calc(100vh - 148px); z-index: 10; display: flex; flex-direction: column; align-items: center; pointer-events: none; }
.timeline-fixed .timeline-line { position: absolute; left: 50%; top: 0; bottom: 0; width: 2px; background: rgba(0,0,0,0.08); transform: translateX(-50%); }
.timeline-scroll { position: relative; z-index: 1; width: 100%; height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 24px; padding: 0; pointer-events: auto; }
.timeline-node { cursor: pointer; padding: 4px; flex-shrink: 0; position: relative; pointer-events: auto; }
.timeline-node .timeline-dot { width: 10px; height: 10px; border-radius: 50%; background: rgba(0,0,0,0.2); transition: all 0.2s ease; }
.timeline-node:hover .timeline-dot { background: #0071e3; transform: scale(1.4); }
.timeline-node.active .timeline-dot { background: #0071e3; box-shadow: 0 0 6px rgba(0,113,227,0.4); }
.timeline-tooltip { position: absolute; right: 28px; top: 50%; transform: translateY(-50%); z-index: 9999; pointer-events: none; white-space: nowrap; }
.tooltip-content { background: rgba(0,0,0,0.75); color: #fff; border-radius: 8px; padding: 8px 14px; font-size: 13px; max-width: 300px; line-height: 1.5; box-shadow: 0 2px 12px rgba(0,0,0,0.15); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); overflow: hidden; text-overflow: ellipsis; }
.tooltip-fade-enter-active { transition: opacity 0.12s ease; }
.tooltip-fade-leave-active { transition: opacity 0.08s ease; }
.tooltip-fade-enter-from { opacity: 0; }
.tooltip-fade-leave-to { opacity: 0; }
.input-area { padding: 12px 24px 16px; background: transparent; flex-shrink: 0; display: flex; flex-direction: column; align-items: center; }
.input-area.drag-over { background: rgba(0,113,227,0.04); }
.upload-preview-area { margin-bottom: 8px; width: 100%; max-width: 640px; }
.upload-images { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 4px; }
.upload-image-item { position: relative; width: 72px; flex-shrink: 0; }
.upload-image-item img { width: 72px; height: 72px; object-fit: cover; border-radius: 10px; border: 1px solid rgba(0,0,0,0.08); }
.upload-image-item .upload-file-name { display: block; font-size: 10px; color: #86868b; text-align: center; margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 72px; }
.upload-files { display: flex; flex-direction: column; gap: 4px; }
.upload-file-item { display: flex; align-items: center; gap: 8px; padding: 6px 10px; background: #ffffff; border: 1px solid rgba(0,0,0,0.08); border-radius: 8px; font-size: 12px; color: #1d1d1f; }
.upload-file-item span { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.upload-remove-btn { width: 20px; height: 20px; border: none; border-radius: 50%; background: rgba(0,0,0,0.08); color: #86868b; cursor: pointer; display: flex; align-items: center; justify-content: center; flex-shrink: 0; padding: 0; position: absolute; top: -6px; right: -6px; }
.upload-file-item .upload-remove-btn { position: static; }
.upload-remove-btn:hover { background: rgba(255,59,48,0.15); color: #ff3b30; }
.input-btn { width: 32px; height: 32px; border: none; border-radius: 50%; background: transparent; color: #86868b; cursor: pointer; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.input-btn:hover { color: #0071e3; }
.input-row { display: flex; align-items: center; gap: 6px; background: #ffffff; border: 1px solid rgba(0,0,0,0.08); border-radius: 28px; padding: 6px 8px 6px 14px; box-shadow: 0 2px 12px rgba(0,0,0,0.04); width: 100%; max-width: 640px; transition: border-color 0.2s, box-shadow 0.2s; }
.input-row:focus-within { border-color: rgba(0,113,227,0.3); box-shadow: 0 2px 16px rgba(0,113,227,0.08); }
.input-field { flex: 1; padding: 8px 0; border: none; background: transparent; font-size: 15px; font-family: inherit; color: #1d1d1f; outline: none; resize: none; min-height: 24px; max-height: 100px; line-height: 1.5; }
.input-field::placeholder { color: #b0b0b5; }
.send-btn { width: 32px; height: 32px; border: none; border-radius: 50%; background: #e5e5ea; color: #b0b0b5; cursor: pointer; display: flex; align-items: center; justify-content: center; flex-shrink: 0; transition: all 0.2s; }
.send-btn.active { background: #0071e3; color: #ffffff; }
.send-btn:disabled { cursor: not-allowed; }
.send-btn.stop { background: #ff3b30; color: #ffffff; animation: pulse 0.8s infinite; }
@keyframes pulse { 0%,100%{box-shadow:0 0 0 0 rgba(255,59,48,0.3)} 50%{box-shadow:0 0 0 8px rgba(255,59,48,0)} }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.input-hint { font-size: 11px; color: #b0b0b5; text-align: center; margin-top: 8px; }
</style>