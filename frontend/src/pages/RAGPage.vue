<!--
文件名: src/pages/RAGPage.vue
功能: 知识库模式 - 上传状态持久化 + 等待动画 + 复制/重新生成
-->
<template>
  <div class="page">
    <header class="topbar">
      <div class="topbar-left">
        <Database :size="18" color="#0071e3" />
        <span class="topbar-title">知识库</span>
        <span class="doc-count">{{ docs.length }} 个文档</span>
      </div>
    </header>

    <div class="body">
      <aside 
        class="file-pool" 
        :class="{ 'drag-over': dragOver }"
        @dragover.prevent="dragOver = true" 
        @dragleave.prevent="dragOver = false" 
        @drop.prevent="onDrop"
      >
        <div class="pool-header">
          <span>文件池</span>
          <div class="pool-header-right">
            <button class="sort-btn" @click="toggleSort" :title="sortLabel"><ArrowUpDown :size="13" /></button>
            <span class="pool-count">{{ selectedCount }}/{{ docs.length }} 已选</span>
          </div>
        </div>

        <div class="pool-list" v-if="sortedDocs.length || uploadingFiles.length">
          <div v-for="(uf, i) in uploadingFiles" :key="'up-' + i" class="pool-item uploading">
            <div class="pool-item-main"><Loader :size="16" class="spin" color="#0071e3" /><span class="pool-name" :title="uf.name">{{ uf.name }}</span></div>
            <div v-if="uf.status === 'error'" class="upload-error"><AlertCircle :size="12" color="#ff3b30" /><span>上传失败</span></div>
          </div>
          <div v-for="(d, i) in sortedDocs" :key="d.id || d" class="pool-item" :class="{ selected: selectedFiles.includes(d.id || d), viewing: viewingFile === (d.id || d) }">
            <div class="pool-item-main" @click="toggleSelect(d)">
              <div class="checkbox" :class="{ checked: selectedFiles.includes(d.id || d) }"><CheckCircle v-if="selectedFiles.includes(d.id || d)" :size="16" color="#0071e3" /><div v-else class="checkbox-empty"></div></div>
              <component :is="fileIcon(d)" :size="16" :color="fileIconColor(d)" />
              <span class="pool-name" :title="d.name || d">{{ d.name || d }}</span>
            </div>
            <div class="pool-actions"><button class="pool-btn" @click.stop="viewFile(d)" title="查看内容"><Eye :size="14" /></button><button class="pool-btn" @click.stop="deleteDoc(d)" title="删除"><Trash2 :size="14" /></button></div>
          </div>
        </div>

        <div v-else class="pool-empty"><Upload :size="28" color="#b0b0b5" /><p>拖拽文档到此处或点击上传</p></div>

        <div class="pool-footer">
          <button class="upload-btn" @click="$refs.du.click()"><Upload :size="14" /> 上传文档</button>
          <button class="delete-all-btn" :disabled="!docs.length" @click="selectedFiles.length ? batchDelete() : deleteAll()"><Trash2 :size="14" /> {{ docs.length ? (selectedFiles.length ? `删除选中 (${selectedFiles.length})` : '删除全部') : '删除全部' }}</button>
          <input ref="du" type="file" accept=".pdf,.txt,.doc,.docx,.md,.csv,.xlsx" hidden multiple @change="uploadDoc" />
        </div>
      </aside>

      <div class="main-area">
        <div class="chat" ref="chatRef">
          <div class="msgs">
            <div v-for="(m, i) in chatStore.messages" :key="i" :class="['msg', m.role]">
              <div v-if="m.role === 'user'" class="bubble user">{{ m.content }}</div>
              <div v-else class="assistant-block">
                <div v-if="m.refs?.length" class="rag-sources">
                  <div class="rag-sources-head" @click="toggleRagSource(i)"><BookOpen :size="13" /><span>{{ ragSourceOpen[i] ? '收起来源' : '引用来源' }} ({{ m.refs.length }})</span></div>
                  <div v-if="ragSourceOpen[i]" class="rag-sources-body">
                    <div v-for="(r, ri) in m.refs" :key="ri" class="rag-source-item"><span class="rag-source-idx">[{{ ri + 1 }}]</span><span class="rag-source-name">{{ r.source }}</span><span v-if="r.snippet" class="rag-source-snippet"> — {{ r.snippet }}</span></div>
                  </div>
                </div>
                <div v-if="m.content" :class="['bubble', 'ai', { stopped: m.stopped }]">
                  <template v-for="(part, pi) in parseContent(m.content)" :key="pi">
                    <CodeBlock v-if="part.type === 'code'" :lang="part.lang" :code="part.code" />
                    <div v-else v-html="part.html"></div>
                  </template>
                </div>
                <div v-if="m.stopped" class="stopped-bar">
                  <AlertCircle :size="14" /> 已停止生成
                  <button v-if="i === chatStore.messages.length - 1" class="regenerate-btn" @click="chatStore.regenerate()"><RefreshCw :size="13" /> 重新生成</button>
                </div>
                <div v-if="!m.isStreaming && m.content" class="actions">
                  <button @click="copy(m.content)"><Copy :size="13" /> 复制</button>
                  <button v-if="i === chatStore.messages.length - 1" @click="chatStore.regenerate()"><RefreshCw :size="13" /> 重新生成</button>
                  <span class="time">{{ fmt(m.timestamp) }}</span>
                </div>
                <div v-if="m.isStreaming && !m.content" class="typing"><span></span><span></span><span></span></div>
              </div>
            </div>
          </div>
        </div>

        <div class="input-area">
          <div class="input-row">
            <textarea v-model="txt" placeholder="基于选中的文档提问..." rows="1" @input="resize" @keydown.enter.exact.prevent="send"></textarea>
            <button v-if="chatStore.isStreaming" class="send-btn stop" @click="chatStore.stopGeneration()"><Square :size="14" /></button>
            <button v-else class="send-btn" :class="{ active: txt.trim() }" :disabled="!txt.trim()" @click="send"><Send :size="16" /></button>
          </div>
          <div class="input-hint">知识库模式 · {{ selectedFiles.length ? '基于 ' + selectedFiles.length + ' 个文档回答' : '选择文档开始提问' }}</div>
        </div>
      </div>

      <aside class="preview-panel" v-if="viewingFile">
        <div class="preview-header"><span :title="viewingFileName">{{ viewingFileName }}</span><button class="preview-close" @click="viewingFile = null"><X :size="16" /></button></div>
        <div class="preview-body">
          <div v-if="viewingLoading" class="preview-loading"><Loader :size="20" class="spin" color="#0071e3" /><span>加载中...</span></div>
          <div v-else-if="viewingContent" class="preview-text">{{ viewingContent }}</div>
          <div v-else class="preview-loading">无法读取文件内容</div>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, nextTick, onMounted } from 'vue'
import { Database, Upload, FileText, FileSpreadsheet, BookOpen, Square, Send, Eye, Trash2, CheckCircle, X, Loader, AlertCircle, ArrowUpDown, Copy, RefreshCw } from 'lucide-vue-next'
import { useChatStore } from '@/stores/chat'
import { useModeStore } from '@/stores/mode'
import { knowledgeApi } from '@/api'
import CodeBlock from '@/components/CodeBlock.vue'

const BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8765'
const chatStore = useChatStore()
const modeStore = useModeStore()
const chatRef = ref(null)
const txt = ref('')
const docs = ref([])
const ragSourceOpen = reactive({})
const selectedFiles = ref([])
const viewingFile = ref(null)
const viewingFileName = ref('')
const viewingContent = ref('')
const viewingLoading = ref(false)
const uploadingFiles = ref([])
const dragOver = ref(false)
const sortOrder = ref('name-asc')

const UPLOADING_KEY = 'rag_uploading_files'

const selectedCount = computed(() => selectedFiles.value.length)
const sortedDocs = computed(() => { const list = [...docs.value]; if (sortOrder.value === 'name-desc') list.reverse(); return list })
const sortLabel = computed(() => sortOrder.value === 'name-asc' ? '按名称排序 ↑' : '按名称排序 ↓')

function toggleSort() { sortOrder.value = sortOrder.value === 'name-asc' ? 'name-desc' : 'name-asc' }
function toggleRagSource(i) { ragSourceOpen[i] = !ragSourceOpen[i] }

function fileIcon(doc) { const n = (doc.name || doc).toLowerCase(); if (n.endsWith('.pdf')) return FileText; if (n.endsWith('.docx') || n.endsWith('.doc')) return FileText; if (n.endsWith('.txt') || n.endsWith('.md')) return FileText; if (n.endsWith('.csv') || n.endsWith('.xlsx') || n.endsWith('.xls')) return FileSpreadsheet; return FileText }
function fileIconColor(doc) { const n = (doc.name || doc).toLowerCase(); if (n.endsWith('.pdf')) return '#ff3b30'; if (n.endsWith('.docx') || n.endsWith('.doc')) return '#0071e3'; if (n.endsWith('.txt') || n.endsWith('.md')) return '#34c759'; if (n.endsWith('.csv') || n.endsWith('.xlsx') || n.endsWith('.xls')) return '#f59e0b'; return '#86868b' }

function onDrop(e) { dragOver.value = false; if (e.dataTransfer.files.length) uploadDoc({ target: { files: e.dataTransfer.files, value: '' } }) }

function persistUploading() {
  localStorage.setItem(UPLOADING_KEY, JSON.stringify(uploadingFiles.value.map(u => ({ name: u.name, status: u.status }))))
}

function uploadFile(file) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${BASE}/rag/upload`)
    xhr.setRequestHeader('X-API-Key', localStorage.getItem('api_key') || '')
    xhr.onload = () => {
      if (xhr.status === 200) {
        try { resolve(JSON.parse(xhr.responseText)) }
        catch { reject(new Error('解析响应失败')) }
      } else {
        reject(new Error('上传失败'))
      }
    }
    xhr.onerror = () => reject(new Error('网络错误'))
    const fd = new FormData()
    fd.append('file', file)
    xhr.send(fd)
  })
}

async function uploadDoc(e) {
  const files = e.target?.files; if (!files?.length) return
  const uploadEntries = []
  for (const file of files) {
    const ext = file.name.split('.').pop()?.toLowerCase()
    const allowed = ['pdf','txt','doc','docx','md','csv','xlsx','xls']
    if (!allowed.includes(ext)) { alert(`不支持的文件格式: .${ext}`); continue }
    const nameExist = docs.value.find(d => (d.name || d) === file.name)
    if (nameExist) { const confirmed = confirm(`文件"${file.name}"已存在于文件池中，是否替换？`); if (!confirmed) continue }
    const uploadEntry = reactive({ name: file.name, status: 'uploading' })
    uploadingFiles.value.push(uploadEntry)
    persistUploading()
    uploadEntries.push({ file, uploadEntry })
  }
  await Promise.all(uploadEntries.map(({ file, uploadEntry }) => (async () => {
    try {
      const result = await uploadFile(file)
      uploadEntry.status = 'done'
      if (result.duplicate) {
        const existingName = result.existing_name || '未知文件'
        const confirmed = confirm(`存在内容相同的文件"${existingName}"，是否仍然上传（替换原文件）？`)
        if (!confirmed) {
          try { await fetch(`${BASE}/rag/collections/${encodeURIComponent(result.collection || file.name)}`, { method: 'DELETE' }) } catch {}
          uploadingFiles.value = uploadingFiles.value.filter(u => u !== uploadEntry)
        }
      }
    } catch (err) {
      uploadEntry.status = 'error'
      console.error('上传失败:', file.name, err)
    } finally {
      uploadingFiles.value = uploadingFiles.value.filter(u => u.status === 'uploading')
      persistUploading()
      await loadDocs()
    }
  })()))
  e.target.value = ''
}

async function batchDelete() {
  const names = docs.value.filter(d => selectedFiles.value.includes(d.id || d)).map(d => d.name || d)
  if (!names.length) return
  const confirmed = confirm(`确定删除选中的 ${names.length} 个文档吗？\n${names.join('\n')}`)
  if (!confirmed) return
  for (const name of names) {
    try { await fetch(`${BASE}/rag/collections/${encodeURIComponent(name)}`, { method: 'DELETE' }) } catch (e) { console.error('删除失败:', name, e) }
  }
  docs.value = docs.value.filter(d => !selectedFiles.value.includes(d.id || d))
  selectedFiles.value = []
  saveSelected()
  if (viewingFile.value && !docs.value.find(d => (d.id || d) === viewingFile.value)) viewingFile.value = null
}

async function deleteAll() {
  const confirmed = confirm(`确定删除全部 ${docs.value.length} 个文档吗？此操作不可恢复。`)
  if (!confirmed) return
  for (const doc of docs.value) {
    try { await fetch(`${BASE}/rag/collections/${encodeURIComponent(doc.name || doc)}`, { method: 'DELETE' }) } catch (e) { console.error('删除失败:', doc.name, e) }
  }
  docs.value = []
  selectedFiles.value = []
  saveSelected()
  viewingFile.value = null
}

function toggleSelect(doc) {
  const id = doc.id || doc
  const idx = selectedFiles.value.indexOf(id)
  if (idx === -1) selectedFiles.value.push(id)
  else selectedFiles.value.splice(idx, 1)
  saveSelected()
}

function saveSelected() {
  localStorage.setItem('rag_selected_files', JSON.stringify(selectedFiles.value))
  const names = docs.value
    .filter(d => selectedFiles.value.includes(d.id || d))
    .map(d => d.name || d)
    .filter(Boolean)
  localStorage.setItem('rag_selected_doc_names', JSON.stringify(names))
}

async function viewFile(doc) {
  const id = doc.id || doc; if (viewingFile.value === id) { viewingFile.value = null; return }
  const name = doc.name || doc; viewingFile.value = id; viewingFileName.value = name; viewingContent.value = ''; viewingLoading.value = true
  try {
    const res = await fetch(`${BASE}/rag/collections/${encodeURIComponent(name)}`)
    if (!res.ok) viewingContent.value = '文件不存在或已被删除'
    else { const data = await res.json(); viewingContent.value = data.content || '文件内容为空' }
  } catch (e) { viewingContent.value = '加载失败: ' + e.message }
  finally { viewingLoading.value = false }
}

async function deleteDoc(doc) {
  const id = doc.id || doc; const name = doc.name || doc
  const confirmed = confirm(`确定删除"${name}"吗？`)
  if (!confirmed) return
  try {
    await fetch(`${BASE}/rag/collections/${encodeURIComponent(name)}`, { method: 'DELETE' })
    docs.value = docs.value.filter(d => (d.id || d) !== id)
    selectedFiles.value = selectedFiles.value.filter(f => f !== id)
    saveSelected()
    if (viewingFile.value === id) viewingFile.value = null
  } catch (e) { console.error('删除失败:', e) }
}

function copy(t) { const d = document.createElement('div'); d.innerHTML = t; navigator.clipboard.writeText(d.textContent || '').catch(() => {}) }

function fmt(t) {
  if (!t) return ''
  const d = new Date(t), now = new Date(), diff = now - d
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
  if (d.toDateString() === now.toDateString()) return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function parseContent(c) { if (!c) return [{ type:'text', html:'' }]; c = c.replace(/```(\w+)([^\n`])/g,'```$1\n$2'); const p = []; const re = /```\s*(\w*)\s*\n([\s\S]*?)```/g; let last = 0, m; while ((m = re.exec(c)) !== null) { if (m.index > last) p.push({ type:'text', html: md(c.slice(last, m.index)) }); p.push({ type:'code', lang: m[1]||'', code: m[2].trim() }); last = m.index + m[0].length } if (last < c.length) p.push({ type:'text', html: md(c.slice(last)) }); if (!p.length) p.push({ type:'text', html: md(c) }); return p }
function md(c) { if (!c) return ''; c = c.replace(/```/g, ''); c = c.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>'); c = c.replace(/\n+/g, '<br>'); return c }

async function loadDocs() {
  try {
    const r = await knowledgeApi.getCollections()
    docs.value = (r.collections || r.documents || []).map(d => { if (typeof d === 'string') return { id: d, name: d }; return d })
    const validIds = docs.value.map(d => d.id || d)
    selectedFiles.value = selectedFiles.value.filter(f => validIds.includes(f))
    saveSelected()
    if (uploadingFiles.value.length === 0) localStorage.removeItem(UPLOADING_KEY)
  } catch (e) { console.error('加载文档失败:', e) }
}

function resize() {}
async function send() { const m = txt.value.trim(); if (!m || chatStore.isStreaming) return; const names = docs.value.filter(d => selectedFiles.value.includes(d.id || d)).map(d => d.name || d).filter(Boolean); chatStore.sendMessage(m, null, false, 'rag', false, null, names); txt.value = '' }
function scrollBottom() { nextTick(() => { if (chatRef.value) chatRef.value.scrollTop = chatRef.value.scrollHeight }) }
function isNearBottom() { const el = chatRef.value; if (!el) return true; return el.scrollHeight - el.scrollTop - el.clientHeight < 60 }

watch(() => modeStore.activeMode, (newMode, oldMode) => { if (oldMode === 'rag') saveSelected(); if (newMode === 'rag') { const saved = localStorage.getItem('rag_selected_files'); if (saved) { try { selectedFiles.value = JSON.parse(saved) } catch {} }; loadDocs() } })
watch(() => chatStore.messages.length, () => nextTick(() => scrollBottom()), { immediate: true })
watch(() => chatStore.messages[chatStore.messages.length - 1]?.content, () => { if (chatStore.isStreaming && isNearBottom()) scrollBottom() })

onMounted(() => {
  const saved = localStorage.getItem('rag_selected_files')
  if (saved) { try { selectedFiles.value = JSON.parse(saved) } catch {} }
  const savedUploading = localStorage.getItem(UPLOADING_KEY)
  if (savedUploading) {
    try {
      const list = JSON.parse(savedUploading)
      if (list.length > 0) {
        uploadingFiles.value = list.map(u => reactive({ name: u.name, status: u.status }))
      }
    } catch {}
  }
  loadDocs()
})
</script>

<style scoped>
.assistant-block { width: 100%; }
.page { display: flex; flex-direction: column; height: 100%; background: #ffffff; }
.topbar { display: flex; align-items: center; justify-content: space-between; padding: 12px 20px; background: #f5f5f7; border-bottom: 1px solid rgba(0,0,0,0.06); flex-shrink: 0; }
.topbar-left { display: flex; align-items: center; gap: 10px; }
.topbar-title { font-size: 15px; font-weight: 600; color: #1d1d1f; }
.doc-count { font-size: 12px; color: #86868b; }
.body { flex: 1; display: flex; overflow: hidden; }
.file-pool { width: 240px; flex-shrink: 0; background: #fafafa; border-right: 1px solid rgba(0,0,0,0.06); display: flex; flex-direction: column; transition: background 0.2s; }
.file-pool.drag-over { background: rgba(0,113,227,0.06); }
.pool-header { display: flex; justify-content: space-between; align-items: center; padding: 14px 16px 10px; font-size: 13px; font-weight: 600; color: #1d1d1f; flex-shrink: 0; }
.pool-header-right { display: flex; align-items: center; gap: 6px; }
.sort-btn { width: 26px; height: 26px; border: none; border-radius: 4px; background: transparent; color: #86868b; cursor: pointer; display: flex; align-items: center; justify-content: center; }
.sort-btn:hover { background: rgba(0,0,0,0.05); color: #1d1d1f; }
.pool-count { font-size: 11px; color: #86868b; font-weight: 400; }
.pool-list { flex: 1; overflow-y: auto; padding: 0 8px 8px; display: flex; flex-direction: column; gap: 2px; }
.pool-item { display: flex; flex-direction: column; padding: 8px 10px; border-radius: 8px; transition: background 0.1s; }
.pool-item:hover { background: rgba(0,0,0,0.03); }
.pool-item.selected { background: rgba(0,113,227,0.04); }
.pool-item.uploading { background: rgba(0,113,227,0.02); }
.pool-item-main { display: flex; align-items: center; gap: 8px; flex: 1; min-width: 0; cursor: pointer; }
.checkbox { flex-shrink: 0; display: flex; align-items: center; }
.checkbox-empty { width: 16px; height: 16px; border: 2px solid rgba(0,0,0,0.15); border-radius: 4px; }
.pool-name { font-size: 13px; color: #1d1d1f; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.pool-actions { display: flex; gap: 2px; margin-top: 4px; }
.pool-btn { width: 28px; height: 28px; border: none; border-radius: 6px; background: transparent; color: #86868b; cursor: pointer; display: flex; align-items: center; justify-content: center; }
.pool-btn:hover { background: rgba(0,0,0,0.05); color: #1d1d1f; }
.pool-empty { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; color: #b0b0b5; font-size: 13px; }
.pool-footer { padding: 10px 12px; border-top: 1px solid rgba(0,0,0,0.06); flex-shrink: 0; display: flex; flex-direction: column; gap: 6px; }
.upload-btn { display: flex; align-items: center; justify-content: center; gap: 6px; width: 100%; padding: 8px 0; border: 1px solid #0071e3; border-radius: 8px; background: transparent; color: #0071e3; cursor: pointer; font-size: 13px; font-family: inherit; transition: all 0.15s; }
.upload-btn:hover { background: #0071e3; color: #fff; }
.delete-all-btn { display: flex; align-items: center; justify-content: center; gap: 6px; width: 100%; padding: 8px 0; border: 1px solid rgba(0,0,0,0.08); border-radius: 8px; background: transparent; color: #86868b; cursor: pointer; font-size: 13px; font-family: inherit; transition: all 0.15s; }
.delete-all-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.delete-all-btn:not(:disabled) { border-color: #ff3b30; color: #ff3b30; }
.delete-all-btn:not(:disabled):hover { background: #ff3b30; color: #fff; }
.upload-error { display: flex; align-items: center; gap: 4px; padding: 2px 0 2px 24px; font-size: 11px; color: #ff3b30; }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.main-area { flex: 1; display: flex; flex-direction: column; min-width: 0; overflow: hidden; }
.chat { flex: 1; overflow-y: auto; padding: 16px 20px; }
.msgs { max-width: 700px; margin: 0 auto; display: flex; flex-direction: column; gap: 14px; }
.msg { display: flex; flex-direction: column; }
.msg.user { align-items: flex-end; }
.msg.assistant { align-items: flex-start; width: 100%; }
.bubble { padding: 10px 16px; border-radius: 14px; font-size: 14px; line-height: 1.6; max-width: 90%; word-break: break-word; }
.bubble.user { background: #0071e3; color: #fff; border-bottom-right-radius: 4px; }
.bubble.ai { background: #ffffff; color: #1d1d1f; border: 1px solid rgba(0,0,0,0.06); border-bottom-left-radius: 4px;  max-width: 90%; }
.bubble.ai.stopped { border-color: rgba(255,149,0,0.25); }
.rag-sources { margin-bottom: 8px; border: 1px solid rgba(0,113,227,0.15); border-radius: 8px; overflow: hidden; }
.rag-sources-head { display: flex; align-items: center; gap: 6px; padding: 6px 10px; font-size: 12px; color: #0071e3; cursor: pointer; background: rgba(0,113,227,0.03); }
.rag-sources-body { padding: 6px 10px; border-top: 1px solid rgba(0,113,227,0.08); }
.rag-source-item { font-size: 11px; color: #86868b; padding: 2px 0; }
.rag-source-idx { color: #0071e3; font-weight: 600; }
.rag-source-name { color: #1d1d1f; font-weight: 500; }
.rag-source-snippet { color: #b0b0b5; }
.typing { display: flex; gap: 4px; }
.typing span { width: 5px; height: 5px; background: #0071e3; border-radius: 50%; animation: bounce 1.2s infinite; opacity: 0.5; }
.typing span:nth-child(2) { animation-delay: 0.2s; }
.typing span:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-4px)} }
.actions { display: flex; align-items: center; gap: 8px; margin-top: 4px; opacity: 0; transition: opacity 0.2s; }
.assistant-block:hover .actions { opacity: 1; }
.actions button { display: flex; align-items: center; gap: 3px; padding: 3px 10px; border: 1px solid rgba(0,0,0,0.08); border-radius: 10px; background: #fff; color: #86868b; cursor: pointer; font-size: 12px; }
.actions button:hover { border-color: #0071e3; color: #0071e3; }
.time { font-size: 11px; color: #b0b0b5; margin-left: auto; }
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
.preview-panel { width: 360px; flex-shrink: 0; background: #fafafa; border-left: 1px solid rgba(0,0,0,0.06); display: flex; flex-direction: column; }
.preview-header { display: flex; justify-content: space-between; align-items: center; padding: 14px 16px; border-bottom: 1px solid rgba(0,0,0,0.06); font-size: 13px; font-weight: 500; color: #1d1d1f; flex-shrink: 0; }
.preview-header span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.preview-close { width: 28px; height: 28px; border: none; border-radius: 6px; background: transparent; color: #86868b; cursor: pointer; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.preview-close:hover { background: rgba(0,0,0,0.05); }
.preview-body { flex: 1; overflow-y: auto; padding: 16px; }
.preview-text { font-size: 13px; color: #1d1d1f; line-height: 1.7; white-space: pre-wrap; }
.preview-loading { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #b0b0b5; padding: 16px 0; }
.input-area { padding: 12px 24px 16px; background: transparent; flex-shrink: 0; display: flex; flex-direction: column; align-items: center; }
.input-row { display: flex; align-items: center; gap: 6px; background: #ffffff; border: 1px solid rgba(0,0,0,0.08); border-radius: 28px; padding: 6px 8px 6px 14px; box-shadow: 0 2px 12px rgba(0,0,0,0.04); width: 100%; max-width: 640px; transition: border-color 0.2s, box-shadow 0.2s; }
.input-row:focus-within { border-color: rgba(0,113,227,0.3); box-shadow: 0 2px 16px rgba(0,113,227,0.08); }
textarea { flex: 1; padding: 8px 0; border: none; background: transparent; font-size: 14px; font-family: inherit; color: #1d1d1f; outline: none; resize: none; min-height: 24px; max-height: 100px; line-height: 1.5; }
textarea::placeholder { color: #b0b0b5; }
.send-btn { width: 32px; height: 32px; border: none; border-radius: 50%; background: #e5e5ea; color: #b0b0b5; cursor: pointer; display: flex; align-items: center; justify-content: center; flex-shrink: 0; transition: all 0.2s; }
.send-btn.active { background: #0071e3; color: #ffffff; }
.send-btn:disabled { cursor: not-allowed; }
.send-btn.stop { background: #ff3b30; color: #ffffff; animation: pulse 0.8s infinite; }
@keyframes pulse { 0%,100%{box-shadow:0 0 0 0 rgba(255,59,48,0.3)} 50%{box-shadow:0 0 0 8px rgba(255,59,48,0)} }
.input-hint { font-size: 11px; color: #b0b0b5; text-align: center; margin-top: 8px; }
</style>