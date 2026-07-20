<!--
文件名: src/pages/EmailPage.vue
功能: 邮件模式 — AI对话独立管理 + 已发送可删除/查看附件 + 预设问题
-->
<template>
  <div class="page">
    <div class="body">
      <div class="editor-panel" :class="{ 'no-assistant': !showAssistant }">
        <div class="field-row">
          <span class="field-label">收件人</span>
          <div class="field-input-wrap">
            <input v-model="mail.to" placeholder="输入邮箱地址，多个用逗号分隔" class="field-input" :disabled="!!viewingSentMail" @blur="validateTo" />
            <span v-if="toError" class="field-error">{{ toError }}</span>
          </div>
          <div class="field-actions">
            <button class="cc-btn" :class="{ active: showCc }" @click="toggleCc" :disabled="!!viewingSentMail">
              抄送<ChevronDown v-if="!showCc" :size="10" /><ChevronUp v-else :size="10" />
            </button>
          </div>
        </div>
        <Transition name="slide">
          <div v-if="showCc" class="cc-fields">
            <div class="field-row"><span class="field-label">抄送</span><input v-model="mail.cc" placeholder="抄送邮箱" class="field-input" :disabled="!!viewingSentMail" /></div>
            <div class="field-row"><span class="field-label">密送</span><input v-model="mail.bcc" placeholder="密送邮箱" class="field-input" :disabled="!!viewingSentMail" /></div>
          </div>
        </Transition>
        <div class="field-row">
          <span class="field-label">主题</span>
          <input v-model="mail.subject" placeholder="邮件主题" class="field-input" maxlength="120" :disabled="!!viewingSentMail" />
        </div>
        <div class="field-row" v-if="signatures.length">
          <span class="field-label">签名</span>
          <div class="sig-select-wrap">
            <select v-model="selectedSig" class="sig-select" @change="applySig" :disabled="!!viewingSentMail">
              <option value="">无签名</option>
              <option v-for="(s,idx) in signatures" :key="idx" :value="s.content">{{ s.name }}</option>
            </select>
            <button class="sig-add-btn" @click="openSigEditor" :disabled="!!viewingSentMail"><Settings :size="13" /></button>
          </div>
        </div>
        <div class="toolbar" v-if="!viewingSentMail">
          <button @click="exec('bold')"><Bold :size="15" /></button>
          <button @click="exec('italic')"><Italic :size="15" /></button>
          <button @click="exec('underline')"><Underline :size="15" /></button>
          <span class="toolbar-sep"></span>
          <button @click="exec('insertUnorderedList')"><List :size="15" /></button>
          <button @click="exec('insertOrderedList')"><ListOrdered :size="15" /></button>
          <span class="toolbar-sep"></span>
          <button @click="insertLink"><Link :size="15" /></button>
          <button @click="cleanFormat"><RemoveFormatting :size="15" /></button>
        </div>
        <div ref="editorRef" class="editor-body" :class="{ disabled: !!viewingSentMail }" :contenteditable="!viewingSentMail" placeholder="邮件正文..." @input="onEditorInput" @paste="onPaste"></div>
        <div v-if="attachments.length && !viewingSentMail" class="attachments-area">
          <div v-for="(a,i) in attachments" :key="i" class="attach-item">
            <FileText :size="14" /><span class="attach-name">{{ a.name }}</span><span class="attach-size">{{ fmtSize(a.size) }}</span>
            <button class="attach-remove" @click="removeAttachment(i)"><X :size="12" /></button>
          </div>
        </div>
        <div v-if="viewingSentAttachments.length && viewingSentMail" class="attachments-area">
          <div v-for="(a,i) in viewingSentAttachments" :key="'sa-'+i" class="attach-item" style="cursor:pointer" @click="previewAttachment(a)">
            <FileText :size="14" /><span class="attach-name">{{ a.name }}</span><span class="attach-size">{{ fmtSize(a.size) }}</span>
          </div>
        </div>
        <div class="editor-footer" v-if="!viewingSentMail">
          <div class="footer-left">
            <label class="attach-btn"><Paperclip :size="15" /><input type="file" hidden multiple @change="onAttachSelect" ref="attachInputRef" /></label>
          </div>
          <div class="footer-right">
            <span v-if="sending" class="sending-hint">发送中...</span>
            <button class="footer-btn save" @click="saveDraft" :disabled="!hasContent"><Save :size="14" /> 保存草稿</button>
            <button class="footer-btn send" @click="confirmSend" :disabled="!canSend || sending"><Send :size="14" /> {{ sending ? '发送中' : '发送' }}</button>
          </div>
        </div>
        <div v-if="sendResult" class="send-result" :class="sendResult.type">
          <CheckCircle v-if="sendResult.type==='success'" :size="14" /><AlertCircle v-else :size="14" />{{ sendResult.msg }}
        </div>
      </div>

      <div class="assistant-panel" v-if="showAssistant">
        <div class="assistant-head"><Sparkles :size="15" color="#0071e3" /><span>AI 邮件助手</span></div>
        <div class="assistant-chat" ref="chatRef">
        <div v-if="!emailMessages.length" class="assistant-empty">
          <Mail :size="28" color="#b0b0b5" /><p>描述需求，AI 帮你起草</p>
          <div v-if="!promptsReady" class="prompts-loading"><span></span><span></span><span></span></div>
          <div v-else class="empty-prompts">
            <button v-for="q in prompts" :key="q" class="prompt-chip" @click="send(q)">{{ q }}</button>
          </div>
          <button v-if="promptsReady" class="refresh-btn" @click="refreshPrompts">换一批</button>
        </div>
          <div v-else class="msgs">
            <div v-for="(m,i) in emailMessages" :key="i" :class="['msg',m.role]">
              <template v-if="m.role==='user'">
              <div v-if="m.isSystemAction" class="bubble system-action">{{ m.content }}</div>
              <div v-else class="bubble user">{{ m.content }}</div>
            </template>
              <div v-else class="assistant-block">
                <div v-if="m.content" class="bubble ai" :class="{ stopped: m.stopped }">
                  <div class="content" v-html="md(m.content)"></div>
                  <span v-if="m.isStreaming && m.content" class="cursor"></span>
                  <div v-if="!m.isStreaming && m.content && !m.accepted && !m.stopped" class="bubble-actions">
                    <button class="accept-btn" @click="acceptDraft(m)"><CheckCircle :size="13" /> 接受</button>
                    <button class="rewrite-btn" @click="rewriteDraft(m)"><RefreshCw :size="13" /> 重写</button>
                    <button class="polish-btn" @click="polishDraft(m)"><Sparkles :size="13" /> 润色</button>
                  </div>
                  <div v-else-if="m.accepted" class="accepted-tag"><CheckCircle :size="13" color="#34c759" /> 已加载到编辑区</div>
                </div>
                <div v-if="m.stopped" class="stopped-bar">
                  <AlertCircle :size="14" /> 已停止生成
                  <button v-if="i === emailMessages.length - 1" class="regenerate-btn" @click="regenerateLast"><RefreshCw :size="13" /> 重新生成</button>
                </div>
                <div v-if="m.isStreaming && !m.content" class="typing"><span></span><span></span><span></span></div>
              </div>
            </div>
          </div>
        </div>
        <div class="assistant-input">
          <div class="input-row">
            <textarea ref="ta" v-model="txt" placeholder="描述邮件需求..." rows="1" @input="resizeAiInput" @keydown.enter.exact.prevent="sendMsg"></textarea>
            <button v-if="isStreamingLocal" class="send-btn stop" @click="stopLocalStream"><Square :size="13" /></button>
            <button v-else class="send-btn" :class="{ active: txt.trim() }" :disabled="!txt.trim() || isStreamingLocal" @click="sendMsg"><Send :size="14" /></button>
          </div>
          <div class="input-hint">AI 邮件助手 · 生成、润色、重写邮件</div>
        </div>
      </div>
    </div>

    <Teleport to="body">
      <Transition name="modal">
        <div v-if="leaveModal" class="modal-overlay" @click.self="leaveModal = false">
          <div class="modal-box">
            <h4>未保存的邮件</h4><p>有未保存的内容，是否保存到草稿箱？</p>
            <div class="modal-btns">
              <button @click="discardLeave">不保存</button><button @click="cancelLeave">取消</button><button class="ok" @click="saveAndLeave">保存到草稿箱</button>
            </div>
          </div>
        </div>
      </Transition>
      <Transition name="modal">
        <div v-if="rwOpen" class="modal-overlay" @click.self="rwOpen = false">
          <div class="modal-box">
            <h4>修改意见</h4><textarea v-model="rwTxt" placeholder="语气更正式..." rows="3" ref="rwTextareaRef"></textarea>
            <div class="modal-btns"><button @click="rwOpen = false">取消</button><button class="ok" @click="doRewrite" :disabled="!rwTxt.trim()">确认</button></div>
          </div>
        </div>
      </Transition>
      <Transition name="modal">
        <div v-if="sigEditorOpen" class="modal-overlay" @click.self="sigEditorOpen = false">
          <div class="modal-box" style="width:440px;">
            <h4>管理签名</h4>
            <div class="sig-list">
              <div v-for="(s,i) in signatures" :key="i" class="sig-item"><span class="sig-name">{{ s.name }}</span><span class="sig-preview">{{ s.content.slice(0,30) }}...</span><button @click="deleteSig(i)"><X :size="14" /></button></div>
              <div v-if="!signatures.length" class="sig-empty">暂无签名</div>
            </div>
            <div class="sig-new"><input v-model="newSigName" placeholder="签名名称" /><textarea v-model="newSigContent" placeholder="签名内容" rows="3"></textarea><button class="ok" @click="addSig" :disabled="!newSigName.trim()||!newSigContent.trim()">添加</button></div>
            <div class="modal-btns" style="margin-top:12px;"><button @click="sigEditorOpen = false">关闭</button></div>
          </div>
        </div>
      </Transition>
      <Transition name="modal">
        <div v-if="showSendConfirm" class="modal-overlay" @click.self="showSendConfirm = false">
          <div class="modal-box">
            <h4>确认发送</h4>
            <p>确定要发送给 <strong>{{ mail.to }}</strong> 吗？</p>
            <div class="modal-btns">
              <button @click="showSendConfirm = false">取消</button>
              <button class="ok" @click="doSend">发送</button>
            </div>
          </div>
        </div>
      </Transition>
      <Transition name="modal">
        <div v-if="previewModal" class="modal-overlay" @click.self="previewModal = null">
          <div class="modal-box" style="max-width:600px;">
            <h4>{{ previewModal.name }}</h4>
            <div v-if="previewModal.type === 'image'" style="text-align:center;">
              <img :src="previewModal.url" style="max-width:100%;max-height:60vh;border-radius:8px;" />
            </div>
            <div v-else style="max-height:50vh;overflow-y:auto;white-space:pre-wrap;font-size:13px;color:#1d1d1f;line-height:1.6;">
              {{ previewModal.content || '无法预览此文件类型' }}
            </div>
            <div class="modal-btns"><button @click="previewModal = null">关闭</button></div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, nextTick, onMounted, onUnmounted, inject } from 'vue'
import { Mail, CheckCircle, RefreshCw, Send, Square, AlertCircle, Save, Sparkles, Bold, Italic, Underline, List, ListOrdered, Link, RemoveFormatting, FileText, Paperclip, X, Settings, ChevronDown, ChevronUp } from 'lucide-vue-next'
import { useChatStore } from '@/stores/chat'
import { useModeStore } from '@/stores/mode'

const sendResult = ref(null)
const chatStore = useChatStore()
const modeStore = useModeStore()
const toast = inject('toast', null)
const refreshDrafts = inject('refreshDrafts', () => {})

function showToast(type, message, action) {
  try {
    if (toast?.value?.addToast) {
      toast.value.addToast(type, message, action)
      return
    }
  } catch {}
  window.dispatchEvent(new CustomEvent('toast', { detail: { type, message, action } }))
}

const BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8765'
const emailPolishPrompt = ref('请润色以下邮件正文：\n\n')
const emailRewritePrompt = ref('请根据修改意见重新生成邮件：\n\n')

const BATCH_SIZE = 3
const allQuestions = ref([])
const prompts = ref([])
const promptsReady = ref(false)

function shuffleArray(arr) { const a = [...arr]; for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1));[a[i], a[j]] = [a[j], a[i]] } return a }
function refreshPrompts() { prompts.value = shuffleArray(allQuestions.value).slice(0, BATCH_SIZE) }

async function loadPrompts() {
  try {
    const [polish, rewrite, questions] = await Promise.all([
      fetch(`${BASE}/chat/prompts/email_polish`).then(r => r.json()),
      fetch(`${BASE}/chat/prompts/email_rewrite`).then(r => r.json()),
      fetch('/src/data/email_questions.json').then(r => r.json()),
    ])
    emailPolishPrompt.value = polish.content || emailPolishPrompt.value
    emailRewritePrompt.value = rewrite.content || emailRewritePrompt.value
    if (questions.length) { allQuestions.value = questions; refreshPrompts() }
  } catch {}
  promptsReady.value = true
}

const emptyMail = () => ({ to: '', cc: '', bcc: '', subject: '', body: '' })
const mail = reactive(emptyMail())
const showCc = ref(false)
const toError = ref('')
const selectedSig = ref('')
const sending = ref(false)
const currentDraftId = ref(null)
const viewingSentMail = ref(null)
const viewingSentAttachments = ref([])
const showAssistant = ref(true)
const hasSaved = ref(false)
const showSendConfirm = ref(false)
const previewModal = ref(null)

const editorRef = ref(null)
const attachments = ref([])
const attachInputRef = ref(null)

const SIGN_KEY = 'localmind_signatures'
const signatures = ref([])
const sigEditorOpen = ref(false)
const newSigName = ref('')
const newSigContent = ref('')

const ta = ref(null)
const chatRef = ref(null)
const txt = ref('')
const rwOpen = ref(false)
const rwTxt = ref('')
const rwTarget = ref(null)
const rwTextareaRef = ref(null)
let sendLock = false
const leaveModal = ref(false)
const leaveResolve = ref(null)

const emailMessages = ref([])
const isStreamingLocal = ref(false)
let localAbortController = null
let currentEmailConvId = null

async function loadDraftConversation(convId) {
  emailMessages.value = []
  currentEmailConvId = convId
  if (!convId) return
  try {
    const r = await fetch(`${BASE}/chat/history?conv_id=${convId}`)
    if (!r.ok) { currentEmailConvId = null; return }
    const data = await r.json()
    emailMessages.value = (data.history || []).map(m => ({
      role: m.role, content: m.content, timestamp: m.timestamp,
      isStreaming: false, accepted: false, stopped: m.stopped || false
    }))
    await nextTick()
    scrollBottom()
  } catch { emailMessages.value = []; currentEmailConvId = null }
}

async function createEmailConversation() {
  const res = await fetch(`${BASE}/chat/conversations/new`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ mode: 'email' })
  })
  const data = await res.json()
  currentEmailConvId = data.conv_id
  return data.conv_id
}

function stopLocalStream() {
  if (localAbortController) {
    localAbortController.abort()
    localAbortController = null
  }
  isStreamingLocal.value = false
}

function send(m) { txt.value = m; sendMsg() }

const hasContent = computed(() => {
  const body = mail.body || (editorRef.value?.innerText?.trim() || '')
  return !!(mail.to.trim() || mail.subject.trim() || body.trim())
})
const canSend = computed(() => {
  const to = mail.to.trim()
  if (!to) return false
  const emails = to.split(',').map(s => s.trim()).filter(Boolean)
  if (!emails.length) return false
  return !sending.value
})

function loadSignatures() { try { signatures.value = JSON.parse(localStorage.getItem(SIGN_KEY) || '[]') } catch { signatures.value = [] } }
function saveSignatures() { localStorage.setItem(SIGN_KEY, JSON.stringify(signatures.value)) }
function openSigEditor() { newSigName.value = ''; newSigContent.value = ''; sigEditorOpen.value = true }
function addSig() { signatures.value.push({ name: newSigName.value.trim(), content: newSigContent.value.trim() }); saveSignatures() }
function deleteSig(idx) { signatures.value.splice(idx, 1); saveSignatures() }
function applySig() {
  if (!selectedSig.value || viewingSentMail.value) return
  const ed = editorRef.value; if (!ed) return
  const html = ed.innerHTML
  const sigIdx = html.lastIndexOf('<hr') > -1 ? html.lastIndexOf('<hr') : html.lastIndexOf('---')
  if (sigIdx > -1) ed.innerHTML = html.slice(0, sigIdx)
  if (selectedSig.value) ed.innerHTML += '<br><br>---<br>' + selectedSig.value.replace(/\n/g, '<br>')
  updateMailBody()
}

function onAttachSelect(e) { if (!e.target.files?.length) return; for (const f of e.target.files) attachments.value.push({ name: f.name, size: f.size, file: f }); e.target.value = '' }
function removeAttachment(idx) { attachments.value.splice(idx, 1) }
function fmtSize(b) { if (b < 1024) return b + ' B'; if (b < 1048576) return (b / 1024).toFixed(1) + ' KB'; return (b / 1048576).toFixed(1) + ' MB' }

function exec(cmd, val = null) { document.execCommand(cmd, false, val); editorRef.value?.focus(); updateMailBody() }
function insertLink() { const u = prompt('输入链接地址：', 'https://'); if (u) exec('createLink', u) }
function cleanFormat() { exec('removeFormat') }
function onEditorInput() { updateMailBody(); hasSaved.value = false }
function onPaste(e) { e.preventDefault(); document.execCommand('insertText', false, e.clipboardData.getData('text/plain')) }
function updateMailBody() { mail.body = editorRef.value?.innerHTML || '' }
function setEditorContent(html) { if (editorRef.value) { editorRef.value.innerHTML = html; updateMailBody() } }

function validateTo() {
  if (!mail.to.trim()) { toError.value = ''; return }
  const emails = mail.to.split(',').map(s => s.trim()).filter(Boolean)
  const invalid = emails.filter(e => !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e))
  toError.value = invalid.length ? `格式错误: ${invalid.join(', ')}` : ''
}
function toggleCc() { showCc.value = !showCc.value }

async function sendMsg() {
  if (sendLock) return
  const m = txt.value.trim()
  if (!m || isStreamingLocal.value) return
  sendLock = true; setTimeout(() => { sendLock = false }, 500)
  if (!currentEmailConvId) { try { await createEmailConversation() } catch (e) { return } }
  emailMessages.value.push({ role: 'user', content: m, timestamp: new Date().toISOString() })
  txt.value = ''; nextTick(() => { if (ta.value) ta.value.style.height = 'auto' })
  await streamEmailMessage(m, false)
}

async function streamEmailMessage(message, isRegenerate = false) {
  if (!currentEmailConvId) return
  const aiMsg = { role: 'assistant', content: '', isStreaming: true, accepted: false, stopped: false }
  emailMessages.value.push(aiMsg)
  const aiIdx = emailMessages.value.length - 1
  chatStore.messages = [...emailMessages.value]
  chatStore.modeConvId = { ...chatStore.modeConvId, email: currentEmailConvId }
  const fd = new FormData()
  fd.append('message', message)
  fd.append('conv_id', currentEmailConvId)
  fd.append('model', 'email')
  if (isRegenerate) fd.append('skip_user', '1')
  isStreamingLocal.value = true
  localAbortController = new AbortController()
  try {
    const resp = await fetch(`${BASE}/chat`, { method: 'POST', body: fd, signal: localAbortController.signal })
    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const jsonStr = line.slice(6).trim()
          if (jsonStr === '[DONE]') { emailMessages.value[aiIdx].isStreaming = false; break }
          try {
            const data = JSON.parse(jsonStr)
            if (data.content) emailMessages.value[aiIdx].content += data.content
            if (data.cancelled) { emailMessages.value[aiIdx].stopped = true; emailMessages.value[aiIdx].isStreaming = false }
          } catch {}
        }
      }
    }
  } catch (e) {
    if (e.name !== 'AbortError') {
      emailMessages.value[aiIdx].content = '请求失败: ' + e.message
    } else {
      emailMessages.value[aiIdx].stopped = true
      const sfd = new FormData()
      sfd.append('content', emailMessages.value[aiIdx].content || '')
      sfd.append('stopped', '1')
      fetch(`${BASE}/chat/save_partial`, { method: 'POST', body: sfd }).catch(() => {})
    }
  }
  emailMessages.value[aiIdx].isStreaming = false
  isStreamingLocal.value = false
  localAbortController = null
  chatStore.messages = [...emailMessages.value]
}

async function saveDraft() {
  if (!hasContent.value) return
  updateMailBody()
  if (!currentEmailConvId) { try { await createEmailConversation() } catch (e) { showToast('error', '创建对话失败'); return } }
  const fd = new FormData()
  fd.append('draft_id', currentDraftId.value || '')
  fd.append('to', mail.to); fd.append('cc', mail.cc); fd.append('bcc', mail.bcc)
  fd.append('subject', mail.subject); fd.append('body', mail.body); fd.append('conv_id', currentEmailConvId)
  try {
    const res = await fetch(`${BASE}/email/drafts`, { method: 'POST', body: fd })
    const data = await res.json()
    currentDraftId.value = data.id; hasSaved.value = true
    showToast('success', '草稿已保存')
    refreshDrafts()
  } catch (e) { showToast('error', '保存草稿失败') }
}

function loadDraft(draft) {
  viewingSentMail.value = null; viewingSentAttachments.value = []; showAssistant.value = true
  mail.to = draft.to || ''; mail.cc = draft.cc || ''; mail.bcc = draft.bcc || ''; mail.subject = draft.subject || ''
  setEditorContent((draft.body || '').replace(/\n/g, '<br>'))
  currentDraftId.value = draft.id; hasSaved.value = true
  if (draft.convId) { loadDraftConversation(draft.convId) }
  else { emailMessages.value = []; currentEmailConvId = null }
}

function viewSent(m) {
  viewingSentMail.value = m; showAssistant.value = false; currentDraftId.value = null; hasSaved.value = true
  mail.to = m.to || ''; mail.cc = m.cc || ''; mail.bcc = m.bcc || ''; mail.subject = m.subject || ''
  setEditorContent((m.body || '').replace(/\n/g, '<br>'))
  viewingSentAttachments.value = (m.attachments || []).map(a => ({
    ...a,
    url: `${BASE}/email/sent/${m.id}/files/${a.name}`,
  }))
}

async function previewAttachment(a) {
  if (a.url) {
    try {
      const res = await fetch(a.url)
      if (!res.ok) { previewModal.value = { name: a.name, type: 'text', content: '文件不存在或已被删除' }; return }
      const blob = await res.blob()
      const isImage = blob.type.startsWith('image/')
      if (isImage) {
        const reader = new FileReader()
        reader.onload = (e) => { previewModal.value = { name: a.name, type: 'image', url: e.target.result } }
        reader.readAsDataURL(blob)
      } else {
        const ext = (a.name || '').split('.').pop()?.toLowerCase()
        const textTypes = ['txt', 'md', 'json', 'js', 'py', 'css', 'html', 'xml', 'csv', 'log', 'yaml', 'yml', 'ini', 'cfg', 'sh', 'bat', 'sql']
        if (textTypes.includes(ext)) {
          const text = await blob.text()
          previewModal.value = { name: a.name, type: 'text', content: text.slice(0, 10000) }
        } else {
          previewModal.value = { name: a.name, type: 'text', content: '此文件类型不支持预览（' + ext.toUpperCase() + ' 格式）' }
        }
      }
    } catch {
      previewModal.value = { name: a.name, type: 'text', content: '加载失败' }
    }
  } else if (a.file) {
    const reader = new FileReader()
    reader.onload = (e) => {
      const isImage = a.file.type.startsWith('image/')
      previewModal.value = { name: a.name, type: isImage ? 'image' : 'text', url: isImage ? e.target.result : null, content: !isImage ? e.target.result : null }
    }
    if (a.file.type.startsWith('image/')) reader.readAsDataURL(a.file)
    else reader.readAsText(a.file)
  } else {
    previewModal.value = { name: a.name, type: 'text', content: '无法预览此文件' }
  }
}

function newMail() {
  if (currentEmailConvId && !currentDraftId.value) {
    fetch(`${BASE}/chat/conversations/${currentEmailConvId}`, { method: 'DELETE' }).catch(() => {})
  }
  viewingSentMail.value = null; viewingSentAttachments.value = []; showAssistant.value = true
  currentDraftId.value = null; hasSaved.value = false
  Object.assign(mail, emptyMail()); setEditorContent(''); attachments.value = []
  emailMessages.value = []; currentEmailConvId = null; chatStore.messages = []
}

function parseEmail(content) {
  const result = { to: '', subject: '', body: '' }
  if (!content) return result
  let text = content.replace(/^```[a-zA-Z]*\n/gm, '').replace(/```$/gm, '').replace(/<br>/g, '\n')
    .replace(/(收件人[:：])/g, '\n$1').replace(/(主题[:：]|标题[:：])/g, '\n$1').replace(/(正文[:：])/g, '\n$1').trim()
  const lines = text.split('\n'); const bodyLines = []; let inBody = false
  for (const line of lines) {
    const t = line.trim()
    if (!t) { if (inBody) bodyLines.push(''); continue }
    const toMatch = t.match(/^收件人[:：]\s*(.+)/i); if (toMatch) { result.to = toMatch[1].trim(); continue }
    const subMatch = t.match(/^(主题|标题)[:：]\s*(.+)/i); if (subMatch) { result.subject = subMatch[2].trim(); continue }
    if (/^正文[:：]$/.test(t)) { inBody = true; continue }
    if (inBody) bodyLines.push(line)
  }
  result.body = bodyLines.join('\n').trim(); if (!result.body) result.body = text.trim()
  return result
}

function acceptDraft(m) {
  const parsed = parseEmail(m.content || '')
  if (!parsed.to) { const em = m.content?.match(/([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/); if (em) parsed.to = em[1] }
  if (!parsed.to) { const um = emailMessages.value.find(msg => msg.role === 'user'); if (um?.content) { const em = um.content.match(/([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/); if (em) parsed.to = em[1] } }
  viewingSentMail.value = null; showAssistant.value = true; hasSaved.value = false
  if (parsed.to) mail.to = parsed.to; if (parsed.subject) mail.subject = parsed.subject
  if (parsed.body) setEditorContent(parsed.body.replace(/\n/g, '<br>'))
  m.accepted = true
  emailMessages.value.forEach(msg => { if (msg !== m && msg.role === 'assistant') msg.accepted = false })
}

function rewriteDraft(m) { rwTarget.value = m; rwTxt.value = ''; rwOpen.value = true; nextTick(() => rwTextareaRef.value?.focus()) }
function doRewrite() {
  if (!rwTxt.value.trim() || !rwTarget.value) return
  const content = (emailRewritePrompt.value || '请根据修改意见重新生成邮件：\n\n') + `修改意见：${rwTxt.value}\n\n原邮件：\n${rwTarget.value.content}`
  const label = '✏️ ' + (rwTxt.value.length > 25 ? rwTxt.value.slice(0, 25) + '...' : rwTxt.value)
  sendMsgWithContent(content, label)
  rwOpen.value = false; rwTarget.value = null
}
function polishDraft(m) {
  sendMsgWithContent(
    (emailPolishPrompt.value || '请润色以下邮件正文：\n\n') + m.content,
    '✨ 润色邮件'
  )
}

function regenerateLast() {
  if (emailMessages.value.length < 2) return
  const last = emailMessages.value[emailMessages.value.length - 1]
  if (last.role !== 'assistant') return
  emailMessages.value.pop()
  const prev = emailMessages.value[emailMessages.value.length - 1]
  if (prev && prev.role === 'user' && prev.isSystemAction) {
    emailMessages.value.pop()
    fetch(`${BASE}/chat/conversations/pop`, { method: 'POST' }).catch(() => {})
  }
  fetch(`${BASE}/chat/conversations/pop`, { method: 'POST' }).catch(() => {})
  const user = [...emailMessages.value].reverse().find(m => m.role === 'user')
  if (!user) return
  streamEmailMessage(user.content, true)
}

async function sendMsgWithContent(content, displayLabel) {
  if (sendLock || isStreamingLocal.value) return
  sendLock = true; setTimeout(() => { sendLock = false }, 500)
  if (!currentEmailConvId) { try { await createEmailConversation() } catch (e) { return } }
  emailMessages.value.push({ role: 'user', content: displayLabel, timestamp: new Date().toISOString(), isSystemAction: true })
  await streamEmailMessage(content, false)
}

function confirmSend() {
  if (!canSend.value || sending.value) return
  if (!mail.to.trim()) { showToast('warning', '请填写收件人'); return }
  showSendConfirm.value = true
}

async function doSend() {
  showSendConfirm.value = false
  await sendMail()
}

async function sendMail() {
  if (!canSend.value || sending.value) return
  if (hasContent.value) await saveDraft()
  sending.value = true
  const bodyText = editorRef.value?.innerText || mail.body
  try {
    const fd = new FormData()
    fd.append('payload', JSON.stringify({
      to: mail.to.split(',').map(s => s.trim()).filter(Boolean),
      cc: mail.cc ? mail.cc.split(',').map(s => s.trim()).filter(Boolean) : [],
      bcc: mail.bcc ? mail.bcc.split(',').map(s => s.trim()).filter(Boolean) : [],
      subject: mail.subject, body: bodyText, bodyHtml: mail.body
    }))
    attachments.value.forEach(a => { if (a.file) fd.append('files', a.file) })
    const res = await fetch(`${BASE}/chat/email/send`, { method: 'POST', body: fd })
    const data = await res.json()
    if (res.ok && data.success) {
      const sf = new FormData()
      sf.append('to', mail.to); sf.append('cc', mail.cc); sf.append('subject', mail.subject); sf.append('body', mail.body)
      sf.append('attachments', JSON.stringify(attachments.value.map(a => ({ name: a.name, size: a.size }))))
      attachments.value.forEach(a => { if (a.file) sf.append('files', a.file, a.name) })
      await fetch(`${BASE}/email/sent`, { method: 'POST', body: sf })
      showToast('success', '邮件已发送')
      if (currentDraftId.value) {
        await fetch(`${BASE}/email/drafts/${currentDraftId.value}`, { method: 'DELETE' })
        currentDraftId.value = null
      }
      if (currentEmailConvId) {
        await fetch(`${BASE}/chat/conversations/${currentEmailConvId}`, { method: 'DELETE' }).catch(() => {})
      }
      refreshDrafts()
      newMail()
    } else { showToast('error', data.error || '发送失败') }
  } catch (e) { showToast('error', '发送失败: ' + e.message) }
  finally { sending.value = false }
}

function checkLeave() {
  if (!hasContent.value || hasSaved.value || viewingSentMail.value) {
    if (!hasContent.value && currentEmailConvId) {
      fetch(`${BASE}/chat/conversations/${currentEmailConvId}`, { method: 'DELETE' }).catch(() => {})
    }
    return Promise.resolve(true)
  }
  return new Promise(resolve => { leaveResolve.value = resolve; leaveModal.value = true })
}

async function saveAndLeave() { await saveDraft(); leaveModal.value = false; leaveResolve.value?.(true) }
async function discardLeave() {
  if (currentEmailConvId) { fetch(`${BASE}/chat/conversations/${currentEmailConvId}`, { method: 'DELETE' }).catch(() => {}) }
  leaveModal.value = false; leaveResolve.value?.(true)
}
function cancelLeave() { leaveModal.value = false; leaveResolve.value?.(false) }
function beforeUnload(e) { if (hasContent.value && !hasSaved.value && !viewingSentMail.value) { e.preventDefault(); e.returnValue = '' } }

function md(c) { return (c || '').replace(/\n/g, '<br>') }
function resizeAiInput() { const el = ta.value; if (el) { el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, 60) + 'px' } }
function scrollBottom() { nextTick(() => { if (chatRef.value) chatRef.value.scrollTo({ top: chatRef.value.scrollHeight, behavior: 'instant' }) }) }

watch(() => emailMessages.value.length, scrollBottom)
watch(emailMessages, scrollBottom, { deep: true })

onMounted(() => { loadSignatures(); loadPrompts(); window.addEventListener('beforeunload', beforeUnload) })
onUnmounted(() => { window.removeEventListener('beforeunload', beforeUnload) })
watch(() => modeStore.activeMode, (n, o) => { if (o === 'email' && n !== 'email' && hasContent.value && !hasSaved.value && !viewingSentMail.value) saveDraft() })

defineExpose({ checkLeave, loadDraft, viewSent, newMail })
</script>

<style scoped>
.page { display: flex; flex-direction: column; height: 100%; background: #ffffff; }
.body { flex: 1; display: flex; overflow: hidden; }
.editor-panel { flex: 1; display: flex; flex-direction: column; padding: 16px 20px; border-right: 1px solid rgba(0,0,0,0.06); overflow-y: auto; min-width: 0; }
.editor-panel.no-assistant { border-right: none; }
.field-row { display: flex; align-items: flex-start; padding: 8px 0; border-bottom: 1px solid rgba(0,0,0,0.04); gap: 10px; }
.field-label { width: 48px; flex-shrink: 0; font-size: 13px; font-weight: 500; color: #86868b; padding-top: 8px; text-align: right; }
.field-input-wrap { flex: 1; min-width: 0; }
.field-input { width: 100%; padding: 8px 0; border: none; font-size: 14px; font-family: inherit; color: #1d1d1f; outline: none; background: transparent; }
.field-input::placeholder { color: #b0b0b5; }
.field-input:disabled { color: #86868b; }
.field-actions { flex-shrink: 0; display: flex; align-items: center; padding-top: 4px; }
.cc-btn { display: inline-flex; align-items: center; gap: 3px; padding: 4px 10px; border: 1px solid rgba(0,0,0,0.06); border-radius: 6px; background: transparent; color: #86868b; font-size: 11px; cursor: pointer; white-space: nowrap; }
.cc-btn:hover, .cc-btn.active { border-color: #0071e3; color: #0071e3; }
.cc-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.field-error { font-size: 11px; color: #ff3b30; margin-top: 2px; }
.cc-fields { overflow: hidden; }
.slide-enter-active, .slide-leave-active { transition: all 0.2s ease; max-height: 120px; }
.slide-enter-from, .slide-leave-to { max-height: 0; opacity: 0; }
.sig-select-wrap { display: flex; align-items: center; gap: 6px; }
.sig-select { padding: 6px 10px; border: 1px solid rgba(0,0,0,0.08); border-radius: 6px; font-size: 13px; color: #1d1d1f; background: #ffffff; outline: none; }
.sig-select:disabled { opacity: 0.5; }
.sig-add-btn { width: 28px; height: 28px; border: none; border-radius: 6px; background: transparent; color: #86868b; cursor: pointer; display: flex; align-items: center; justify-content: center; }
.sig-add-btn:disabled { opacity: 0.3; cursor: not-allowed; }
.sig-add-btn:hover:not(:disabled) { background: rgba(0,0,0,0.05); color: #1d1d1f; }
.toolbar { display: flex; align-items: center; gap: 2px; padding: 8px 0; border-bottom: 1px solid rgba(0,0,0,0.06); flex-shrink: 0; }
.toolbar button { width: 30px; height: 30px; border: none; border-radius: 6px; background: transparent; color: #86868b; cursor: pointer; display: flex; align-items: center; justify-content: center; }
.toolbar button:hover { background: rgba(0,0,0,0.05); color: #1d1d1f; }
.toolbar-sep { width: 1px; height: 16px; background: rgba(0,0,0,0.08); margin: 0 4px; }
.editor-body { flex: 1; min-height: 180px; padding: 12px 0; font-size: 14px; line-height: 1.7; color: #1d1d1f; outline: none; overflow-y: auto; word-break: break-word; }
.editor-body:empty::before { content: attr(placeholder); color: #b0b0b5; }
.editor-body.disabled { opacity: 0.6; pointer-events: none; user-select: none; }
.attachments-area { padding: 8px 0; border-top: 1px solid rgba(0,0,0,0.04); display: flex; flex-wrap: wrap; gap: 6px; }
.attach-item { display: flex; align-items: center; gap: 6px; padding: 6px 10px; background: #f5f5f7; border-radius: 8px; font-size: 12px; color: #1d1d1f; }
.attach-name { max-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.attach-size { color: #86868b; font-size: 11px; }
.attach-remove { width: 20px; height: 20px; border: none; border-radius: 50%; background: transparent; color: #86868b; cursor: pointer; display: flex; align-items: center; justify-content: center; }
.attach-remove:hover { background: rgba(255,59,48,0.1); color: #ff3b30; }
.editor-footer { display: flex; align-items: center; justify-content: space-between; padding: 10px 0 0; border-top: 1px solid rgba(0,0,0,0.06); flex-shrink: 0; margin-top: auto; }
.footer-left { display: flex; align-items: center; gap: 12px; }
.attach-btn { display: flex; align-items: center; justify-content: center; width: 32px; height: 32px; border: 1px solid rgba(0,0,0,0.08); border-radius: 8px; background: #ffffff; color: #86868b; cursor: pointer; }
.attach-btn:hover { border-color: #0071e3; color: #0071e3; }
.attach-btn input { display: none; }
.auto-save-hint { font-size: 12px; color: #34c759; }
.footer-right { display: flex; align-items: center; gap: 8px; }
.sending-hint { font-size: 12px; color: #0071e3; }
.footer-btn { display: inline-flex; align-items: center; gap: 5px; padding: 9px 18px; border: 1px solid rgba(0,0,0,0.08); border-radius: 10px; font-size: 13px; cursor: pointer; }
.footer-btn.save { background: #ffffff; color: #1d1d1f; }
.footer-btn.save:hover:not(:disabled) { border-color: #0071e3; color: #0071e3; }
.footer-btn.send { background: #0071e3; border: none; color: #ffffff; font-weight: 500; }
.footer-btn.send:hover:not(:disabled) { background: #0077ed; }
.footer-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.send-result { display: flex; align-items: center; gap: 6px; font-size: 13px; padding: 8px 12px; border-radius: 8px; margin-top: 8px; }
.send-result.success { background: rgba(52,199,89,0.08); color: #34c759; }
.send-result.error { background: rgba(255,59,48,0.08); color: #ff3b30; }

.assistant-panel { width: 320px; flex-shrink: 0; display: flex; flex-direction: column; background: #fafafa; }
.assistant-head { display: flex; align-items: center; gap: 6px; padding: 12px 16px; border-bottom: 1px solid rgba(0,0,0,0.06); font-size: 13px; font-weight: 500; color: #1d1d1f; flex-shrink: 0; background: #ffffff; }
.assistant-chat { flex: 1; overflow-y: auto; padding: 12px 14px; }
.assistant-empty { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; gap: 10px; color: #b0b0b5; font-size: 13px; }
.prompts-loading { display: flex; gap: 6px; padding: 12px 0; }
.prompts-loading span { width: 6px; height: 6px; background: #0071e3; border-radius: 50%; opacity: 0.5; animation: bounce 1.2s infinite; }
.prompts-loading span:nth-child(2) { animation-delay: 0.2s; }
.prompts-loading span:nth-child(3) { animation-delay: 0.4s; }
.empty-prompts { display: flex; flex-direction: column; gap: 8px; max-width: 280px; margin-top: 12px; }
.prompt-chip { padding: 10px 14px; border-radius: 12px; border: 1px solid rgba(0,0,0,0.08); background: #ffffff; color: #1d1d1f; cursor: pointer; font-size: 13px; font-family: inherit; text-align: center; transition: all 0.15s; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.prompt-chip:hover { border-color: #0071e3; color: #0071e3; background: rgba(0,113,227,0.04); }
.refresh-btn { padding: 6px 16px; border-radius: 14px; border: 1px solid rgba(0,0,0,0.08); background: transparent; color: #86868b; cursor: pointer; font-size: 12px; font-family: inherit; margin-top: 6px; transition: all 0.15s; }
.refresh-btn:hover { border-color: #0071e3; color: #0071e3; background: rgba(0,113,227,0.04); }
.msgs { display: flex; flex-direction: column; gap: 10px; }
.msg { max-width: 94%; }
.msg.user { align-self: flex-end; }
.msg.assistant { align-self: flex-start; }
.bubble { padding: 9px 13px; border-radius: 14px; font-size: 13px; line-height: 1.5; word-break: break-word; }
.bubble.user { background: #0071e3; color: #ffffff; border-bottom-right-radius: 4px; }
.bubble.ai { background: #ffffff; color: #1d1d1f; border: 1px solid rgba(0,0,0,0.06); border-bottom-left-radius: 4px; }
.bubble.ai.stopped { border-color: rgba(255,149,0,0.25); }
.typing { display: flex; gap: 4px; }
.typing span { width: 5px; height: 5px; background: #0071e3; border-radius: 50%; animation: bounce 1.2s infinite; opacity: 0.5; }
.typing span:nth-child(2) { animation-delay: 0.2s; }
.typing span:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-4px)} }
.cursor { color: #0071e3; animation: blink 1s infinite; }
@keyframes blink { 0%,50%{opacity:1} 51%,100%{opacity:0} }
.bubble-actions { display: flex; gap: 6px; margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(0,0,0,0.06); }
.accept-btn { display: inline-flex; align-items: center; gap: 3px; padding: 5px 12px; border: none; border-radius: 7px; background: #0071e3; color: #ffffff; font-size: 11px; cursor: pointer; }
.rewrite-btn, .polish-btn { display: inline-flex; align-items: center; gap: 3px; padding: 5px 12px; border: 1px solid rgba(0,0,0,0.08); border-radius: 7px; background: #ffffff; color: #1d1d1f; font-size: 11px; cursor: pointer; }
.rewrite-btn:hover, .polish-btn:hover { border-color: #0071e3; color: #0071e3; }
.accepted-tag { font-size: 12px; color: #34c759; margin-top: 6px; display: flex; align-items: center; gap: 4px; }
.stopped-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  padding: 10px 14px;
  background: #fff3cd;
  border: 1px solid rgba(255,149,0,0.2);
  border-radius: 10px;
  font-size: 13px;
  color: #856404;
  font-weight: 500;
}
.stopped-bar .regenerate-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 14px;
  border: 1px solid #0071e3;
  border-radius: 8px;
  background: #ffffff;
  color: #0071e3;
  cursor: pointer;
  font-size: 12px;
  font-family: inherit;
  font-weight: 500;
  margin-left: auto;
}
.stopped-bar .regenerate-btn:hover {
  background: #0071e3;
  color: #ffffff;
}
.assistant-input { padding: 8px 14px 12px; flex-shrink: 0; }
.input-row { display: flex; align-items: flex-end; gap: 6px; background: transparent; border: 1px solid rgba(0,0,0,0.06); border-radius: 28px; padding: 6px 8px 6px 14px; transition: border-color 0.2s; }
.input-row:focus-within { border-color: rgba(0,113,227,0.3); }
.input-row textarea { flex: 1; padding: 8px 0; border: none; background: transparent; font-size: 15px; font-weight: 400; font-family: inherit; color: #1d1d1f; outline: none; resize: none; min-height: 24px; max-height: 60px; }
.input-row textarea::placeholder { color: #b0b0b5; }
.send-btn { width: 32px; height: 32px; border: none; border-radius: 50%; background: #e5e5ea; color: #b0b0b5; cursor: pointer; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.send-btn.active { background: #0071e3; color: #ffffff; }
.send-btn:disabled { cursor: not-allowed; }
.send-btn.stop { background: #ff3b30; color: #ffffff; }
.input-hint { font-size: 11px; color: #b0b0b5; text-align: center; margin-top: 8px; }
.bubble.system-action {
  background: rgba(0,113,227,0.06);
  color: #0071e3;
  font-size: 13px;
  font-weight: 500;
  text-align: center;
  max-width: 240px;
  margin: 0 auto;
  border-radius: 10px;
  padding: 8px 14px;
}
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.35); backdrop-filter: blur(4px); z-index: 1000; display: flex; align-items: center; justify-content: center; }
.modal-box { width: 380px; background: #ffffff; border-radius: 16px; padding: 24px; box-shadow: 0 16px 48px rgba(0,0,0,0.15); }
.modal-box h4 { margin: 0 0 6px; font-size: 16px; font-weight: 600; color: #1d1d1f; }
.modal-box p { margin: 0 0 16px; font-size: 14px; color: #86868b; }
.modal-box textarea { width: 100%; padding: 10px; border: 1px solid rgba(0,0,0,0.1); border-radius: 10px; font-size: 14px; color: #1d1d1f; resize: none; outline: none; box-sizing: border-box; }
.modal-box textarea:focus { border-color: #0071e3; }
.modal-btns { display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }
.modal-btns button { padding: 8px 18px; border: 1px solid rgba(0,0,0,0.08); border-radius: 10px; background: #ffffff; color: #1d1d1f; font-size: 13px; cursor: pointer; }
.modal-btns button:hover { background: #f5f5f7; }
.modal-btns button.ok { background: #0071e3; border: none; color: #ffffff; }
.modal-btns button.ok:hover { background: #0077ed; }
.modal-btns button.ok:disabled { opacity: 0.4; cursor: not-allowed; }
.sig-list { max-height: 180px; overflow-y: auto; margin-bottom: 12px; }
.sig-item { display: flex; align-items: center; gap: 8px; padding: 8px; border-radius: 8px; }
.sig-item:hover { background: #f5f5f7; }
.sig-name { font-size: 13px; font-weight: 500; width: 90px; flex-shrink: 0; }
.sig-preview { font-size: 12px; color: #86868b; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sig-item button { border: none; background: transparent; color: #b0b0b5; cursor: pointer; }
.sig-item button:hover { color: #ff3b30; }
.sig-empty { font-size: 13px; color: #b0b0b5; padding: 12px; text-align: center; }
.sig-new { display: flex; flex-direction: column; gap: 8px; }
.sig-new input, .sig-new textarea { width: 100%; padding: 8px; border: 1px solid rgba(0,0,0,0.1); border-radius: 8px; font-size: 13px; color: #1d1d1f; outline: none; box-sizing: border-box; }
.sig-new input:focus, .sig-new textarea:focus { border-color: #0071e3; }
.sig-new button.ok { align-self: flex-end; padding: 6px 16px; }
.modal-enter-active, .modal-leave-active { transition: all 0.2s ease; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-from .modal-box, .modal-leave-to .modal-box { transform: scale(0.95); }
</style>