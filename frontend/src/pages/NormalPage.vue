<!--
文件名: src/pages/NormalPage.vue
功能: 日常模式 - 三点动画无气泡，和Agent模式一致
-->
<template>
  <div class="page">
    <div class="chat" ref="chatRef">
      <div v-if="!chatStore.messages.length" class="empty">
        <div class="empty-icon"><MessageCircle :size="40" color="#0071e3" /></div>
        <h2>日常模式</h2><p>随时提问，全能应答</p>
        <div v-if="!promptsReady" class="prompts-loading"><span></span><span></span><span></span></div>
        <div v-else class="empty-prompts"><button v-for="q in prompts" :key="q" class="prompt-chip" @click="send(q)">{{ q }}</button></div>
        <button v-if="promptsReady" class="refresh-btn" @click="refreshPrompts">换一批</button>
      </div>

      <div v-else class="msgs">
        <div v-for="(m, i) in chatStore.messages" :key="i" :class="['msg', m.role]">
          <template v-if="m.role === 'user'">
            <div v-if="m.files && m.files.length" class="attach-card">
              <div v-if="m.files.some(f => f && (f.type === 'image' || isImageFile(f.name)))" class="attach-images">
                <div v-for="(f, fi) in m.files.filter(f => f && (f.type === 'image' || isImageFile(f.name)))" :key="'img-'+fi" class="attach-image-item" @click="previewImage(f)">
                  <img v-if="f.thumb || f.url" :src="f.thumb || f.url" :alt="f.name" /><Image v-else :size="32" /><span class="attach-image-label">{{ f.name }}</span>
                </div>
              </div>
              <div v-if="m.files.some(f => f && !(f.type === 'image' || isImageFile(f.name)))" class="attach-files">
                <div v-for="(f, fi) in m.files.filter(f => f && !(f.type === 'image' || isImageFile(f.name)))" :key="'file-'+fi" class="attach-file-row"><FileText :size="14" /><span class="attach-file-name">{{ f.name }}</span></div>
              </div>
            </div>
            <div v-if="m.content && m.content !== '新对话'" class="bubble user"><div class="content">{{ m.content }}</div></div>
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
                <Loader v-if="!isAnalyzeDone(m.analyzeStatus)" :size="12" class="spin" color="#f59e0b" />
                <CheckCircle v-else :size="12" color="#34c759" />
              </span>
            </div>
            <div v-if="m.thinking" class="think" @click="toggleThink(i)"><Brain :size="13" /> <span>{{ thinkOpen[i] ? '收起思考' : '思考过程' }}</span></div>
            <div v-if="thinkOpen[i] && m.thinking" class="think-text">{{ m.thinking }}</div>
            <div v-if="m.memoryState" class="memory-status"><Database :size="13" /> <span>{{ m.memoryState.status }}</span></div>
            <div v-if="m.content" :class="['bubble', 'assistant', { stopped: m.stopped }]">
              <template v-for="(part, pi) in parseContent(m.content)" :key="pi">
                <CodeBlock v-if="part.type === 'code'" :lang="part.lang" :code="part.code" />
                <div v-else class="content" v-html="part.html"></div>
              </template>
              <span v-if="m.isStreaming && m.content" class="cursor"></span>
              <div v-if="!m.isStreaming && m.content" class="actions">
                <button @click="copy(m.content)"><Copy :size="13" /> 复制</button>
                <button v-if="i === chatStore.messages.length - 1" @click="chatStore.regenerate()"><RefreshCw :size="13" /> 重新生成</button>
                <span class="time">{{ fmt(m.timestamp) }}</span>
              </div>
              <div v-if="m.suggestions?.length" class="sugs"><button v-for="s in m.suggestions" :key="s" @click="send(s)">{{ s }}</button></div>
            </div>
            <div v-if="m.stopped" class="stopped-bar">
              <AlertCircle :size="14" /> 已停止生成
              <button v-if="i === chatStore.messages.length - 1" class="regenerate-btn" @click="chatStore.regenerate()"><RefreshCw :size="13" /> 重新生成</button>
            </div>
            <div v-if="m.isStreaming && !m.content && !m.analyzeStatus" class="typing"><span></span><span></span><span></span></div>
          </div>
        </div>
      </div>
    </div>

    <Teleport to="body"><div v-if="previewImageSrc" class="image-overlay" @click="previewImageSrc = null"><img :src="previewImageSrc" /><button class="image-overlay-close" @click="previewImageSrc = null"><X :size="20" /></button></div></Teleport>

    <div class="input-area" @dragover.prevent="dragOver = true" @dragleave.prevent="dragOver = false" @drop.prevent="onDrop" :class="{ 'drag-over': dragOver }">
      <div v-if="uploadFiles.length" class="upload-preview-area">
        <div class="upload-images"><div v-for="(f, i) in imageFiles" :key="'up-img-'+i" class="upload-image-item"><img :src="f.thumb" :alt="f.name" @click="previewImage(f)" /><button class="upload-remove-btn" @click="removeUploadFile(f.id)"><X :size="12" /></button><span class="upload-file-name">{{ f.name }}</span></div></div>
        <div class="upload-files"><div v-for="(f, i) in docFiles" :key="'up-doc-'+i" class="upload-file-item"><FileText :size="16" /><span>{{ f.name }}</span><button class="upload-remove-btn" @click="removeUploadFile(f.id)"><X :size="12" /></button></div></div>
      </div>
      <div class="input-row">
        <div class="input-left">
          <div class="model-switcher" ref="modelRef">
            <button class="model-btn" :class="{ active: showModelMenu }" @click="showModelMenu = !showModelMenu"><Zap v-if="fastMode" :size="18" /><Brain v-else :size="18" /></button>
            <Transition name="popover"><div v-if="showModelMenu" class="model-menu"><button class="model-option" :class="{ selected: fastMode }" @click="selectModel('fast')"><div class="option-left"><div class="option-icon fast"><Zap :size="18" /></div><div class="option-info"><span class="option-name">快速模式</span><span class="option-desc">轻快响应</span></div></div><CheckCircle v-if="fastMode" :size="16" color="#0071e3" /></button><button class="model-option" :class="{ selected: !fastMode }" @click="selectModel('deep')"><div class="option-left"><div class="option-icon deep"><Brain :size="18" /></div><div class="option-info"><span class="option-name">深度思考</span><span class="option-desc">逻辑推理</span></div></div><CheckCircle v-if="!fastMode" :size="16" color="#0071e3" /></button></div></Transition>
          </div>
          <button class="input-btn" @click="$refs.fi.click()"><Paperclip :size="18" /></button>
          <input ref="fi" type="file" hidden multiple @change="onFileSelect" accept="image/*,.pdf,.doc,.docx,.txt,.csv,.xlsx,.xls,.py,.js,.json" />
        </div>
        <textarea ref="ta" v-model="txt" class="input-field" placeholder="输入问题，或拖拽文件到此处..." rows="1" @input="resize" @keydown.enter.exact.prevent="sendMsg" @paste="onPaste"></textarea>
        <button v-if="chatStore.isStreaming" class="send-btn stop" @click="chatStore.stopGeneration()"><Square :size="14" /></button>
        <button v-else class="send-btn" :class="{ active: txt.trim() || uploadFiles.length }" :disabled="!txt.trim() && !uploadFiles.length" @click="sendMsg"><Send :size="16" /></button>
      </div>
      <div class="input-hint">{{ fastMode ? '快速模式 · 轻快响应' : '深度思考 · 逻辑推理' }}<span v-if="uploadFiles.length"> · 已选 {{ uploadFiles.length }} 个文件</span></div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { MessageCircle, Brain, Copy, RefreshCw, AlertCircle, Zap, Paperclip, Send, Square, FileText, X, CheckCircle, Database, Image, Loader } from 'lucide-vue-next'
import { useChatStore } from '@/stores/chat'
import CodeBlock from '@/components/CodeBlock.vue'

const MAX_FILES = 6; const MAX_IMAGE_SIZE = 10 * 1024 * 1024; const BATCH_SIZE = 6
const chatStore = useChatStore(); const chatRef = ref(null); const ta = ref(null); const txt = ref(''); const fastMode = ref(true); const showModelMenu = ref(false); const modelRef = ref(null)
const thinkOpen = reactive({}); const dragOver = ref(false); const previewImageSrc = ref(null)
const uploadFiles = ref([]); let fileIdCounter = 0; let sendLock = false
const imageFiles = computed(() => uploadFiles.value.filter(f => f.type === 'image'))
const docFiles = computed(() => uploadFiles.value.filter(f => f.type !== 'image'))
const defaultPrompts = ['Python 怎么学？','帮我写一份周报','什么是机器学习？','推荐一本好书','写一个快速排序算法','如何搭建个人博客？','解释一下 RESTful API','什么是 Docker？','帮我写一个 Shell 脚本']
const allQuestions = ref([]); const prompts = ref([]); const promptsReady = ref(false)

function shuffleArray(arr) { const a = [...arr]; for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1));[a[i], a[j]] = [a[j], a[i]] } return a }
function refreshPrompts() { const s = allQuestions.value.length ? allQuestions.value : defaultPrompts; prompts.value = shuffleArray(s).slice(0, BATCH_SIZE) }
async function loadPrompts() { try { const r = await fetch('/src/data/normal_questions.json'); if (r.ok) { const d = await r.json(); if (d.length) allQuestions.value = d } } catch (e) {}; refreshPrompts(); promptsReady.value = true }
function getFileType(f) { const e = f.name.split('.').pop()?.toLowerCase() || ''; return ['jpg','jpeg','png','gif','bmp','webp','svg'].includes(e) ? 'image' : 'file' }
function isImageFile(n) { if (!n) return false; return ['jpg','jpeg','png','gif','bmp','webp','svg'].includes(n.split('.').pop()?.toLowerCase()) }
function isAnalyzeDone(t) { return t?.includes('分析完成') || t?.includes('已分析') }
function createThumbnail(f) { return new Promise(r => { if (getFileType(f) !== 'image') { r(null); return }; const rd = new FileReader(); rd.onload = e => { const img = new window.Image(); img.onload = () => { const c = document.createElement('canvas'); const mw = 120, mh = 120; let w = img.width, h = img.height; if (w > h) { if (w > mw) { h *= mw / w; w = mw } } else { if (h > mh) { w *= mh / h; h = mh } }; c.width = w; c.height = h; c.getContext('2d').drawImage(img, 0, 0, w, h); r(c.toDataURL('image/jpeg', 0.7)) }; img.src = e.target.result }; rd.readAsDataURL(f) }) }
async function addFiles(fl) { for (const f of fl) { if (uploadFiles.value.length >= MAX_FILES) break; if (f.size > MAX_IMAGE_SIZE && getFileType(f) === 'image') continue; const t = getFileType(f); const id = ++fileIdCounter; uploadFiles.value.push({ id, file: f, name: f.name, type: t, url: t === 'image' ? URL.createObjectURL(f) : null, thumb: t === 'image' ? await createThumbnail(f) : null }) } }
function removeUploadFile(id) { const i = uploadFiles.value.findIndex(f => f.id === id); if (i !== -1) { const f = uploadFiles.value[i]; if (f.url) URL.revokeObjectURL(f.url); uploadFiles.value.splice(i, 1) } }
function onFileSelect(e) { if (e.target.files.length) addFiles(e.target.files); e.target.value = '' }
function onDrop(e) { dragOver.value = false; if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files) }
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
function previewImage(f) { previewImageSrc.value = f.url || f.thumb }

function parseContent(c) { if (!c) return [{ type:'text', html:'' }]; c = c.replace(/```(\w+)([^\n`])/g,'```$1\n$2'); const p = []; const re = /```\s*(\w*)\s*\n([\s\S]*?)```/g; let last = 0, m; while ((m = re.exec(c)) !== null) { if (m.index > last) p.push({ type:'text', html: md(c.slice(last, m.index)) }); p.push({ type:'code', lang: m[1]||'', code: m[2].trim() }); last = m.index + m[0].length } if (last < c.length) p.push({ type:'text', html: md(c.slice(last)) }); if (!p.length) p.push({ type:'text', html: md(c) }); return p }
function md(c) { if (!c) return ''; c = c.replace(/```/g,''); c = c.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>'); c = c.replace(/\n/g,'<br>'); return c }

function fmt(t) {
  if (!t) return ''
  const d = new Date(t), now = new Date(), diff = now - d
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
  if (d.toDateString() === now.toDateString()) {
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  }
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
function copy(t) { const d = document.createElement('div'); d.innerHTML = t; navigator.clipboard.writeText(d.textContent || '').catch(() => {}) }
function toggleThink(i) { thinkOpen[i] = !thinkOpen[i] }
function resize() { const el = ta.value; if (el) { el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, 120) + 'px' } }
async function sendMsg() { if (sendLock) return; const m = txt.value.trim(); if (!m && !uploadFiles.value.length) return; if (chatStore.isStreaming) return; sendLock = true; setTimeout(() => { sendLock = false }, 500); const model = fastMode.value ? 'fast' : 'reasoning'; const fp = uploadFiles.value.map(f => ({ name: f.name, type: f.type, file: f.file, thumb: f.thumb, url: f.url })); chatStore.sendMessage(m, fp.length ? fp : null, false, model); txt.value = ''; uploadFiles.value = []; nextTick(() => { if (ta.value) ta.value.style.height = 'auto' }) }
function send(m) { if (sendLock) return; if (chatStore.isStreaming) return; sendLock = true; setTimeout(() => { sendLock = false }, 500); chatStore.sendMessage(m, null, false, fastMode.value ? 'fast' : 'reasoning') }
function selectModel(t) { fastMode.value = t === 'fast'; showModelMenu.value = false }
function clickOutside(e) { if (modelRef.value && !modelRef.value.contains(e.target)) showModelMenu.value = false }
function scrollBottom() { nextTick(() => { if (chatRef.value) chatRef.value.scrollTo({ top: chatRef.value.scrollHeight, behavior: 'instant' }) }) }
function isNearBottom() { const el = chatRef.value; if (!el) return true; return el.scrollHeight - el.scrollTop - el.clientHeight < 60 }

onMounted(() => { document.addEventListener('click', clickOutside); loadPrompts() })
onUnmounted(() => document.removeEventListener('click', clickOutside))

watch(() => chatStore.messages.length, () => nextTick(() => scrollBottom()), { immediate: true })
watch(() => chatStore.messages[chatStore.messages.length - 1]?.content, () => { if (chatStore.isStreaming && isNearBottom()) scrollBottom() })
</script>

<style scoped>
.page { display: flex; flex-direction: column; height: 100%; background: #ffffff; }
.chat { flex: 1; overflow-y: auto; padding: 20px 24px; }
.empty { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; gap: 8px; }
.empty-icon { margin-bottom: 4px; }
.empty h2 { font-size: 18px; font-weight: 600; color: #1d1d1f; }
.empty p { font-size: 14px; color: #86868b; }
.prompts-loading { display: flex; gap: 6px; padding: 12px 0; }
.prompts-loading span { width: 6px; height: 6px; background: #0071e3; border-radius: 50%; opacity: 0.5; animation: bounce 1.2s infinite; }
.prompts-loading span:nth-child(2) { animation-delay: 0.2s; }
.prompts-loading span:nth-child(3) { animation-delay: 0.4s; }
.empty-prompts { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; max-width: 520px; margin-top: 12px; }
@media (max-width: 600px) { .empty-prompts { grid-template-columns: repeat(2, 1fr); } }
.prompt-chip { padding: 10px 14px; border-radius: 12px; border: 1px solid rgba(0,0,0,0.08); background: #ffffff; color: #1d1d1f; cursor: pointer; font-size: 13px; font-family: inherit; text-align: center; transition: all 0.15s; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.prompt-chip:hover { border-color: #0071e3; color: #0071e3; background: rgba(0,113,227,0.04); transform: translateY(-1px); }
.refresh-btn { padding: 6px 16px; border-radius: 14px; border: 1px solid rgba(0,0,0,0.08); background: transparent; color: #86868b; cursor: pointer; font-size: 12px; font-family: inherit; margin-top: 14px; transition: all 0.15s; }
.refresh-btn:hover { border-color: #0071e3; color: #0071e3; background: rgba(0,113,227,0.04); }
.msgs { max-width: 720px; margin: 0 auto; display: flex; flex-direction: column; gap: 16px; }
.msg.user { align-self: flex-end; display: flex; flex-direction: column; align-items: flex-end; max-width: 80%; }
.msg.assistant { align-self: flex-start; width: 100%; }
.assistant-block { width: 100%; }
.attach-card { background: #f0f0f3; border-radius: 16px; padding: 10px; margin-bottom: 6px; max-width: 100%; }
.attach-images { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 6px; }
.attach-images:last-child { margin-bottom: 0; }
.attach-image-item { cursor: pointer; flex-shrink: 0; }
.attach-image-item img { width: 64px; height: 64px; object-fit: cover; border-radius: 8px; display: block; }
.attach-image-label { display: block; font-size: 10px; color: #86868b; text-align: center; margin-top: 2px; max-width: 64px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.attach-files { display: flex; flex-direction: column; gap: 3px; }
.attach-file-row { display: flex; align-items: center; gap: 6px; padding: 5px 8px; background: rgba(0,0,0,0.03); border-radius: 6px; color: #86868b; }
.attach-file-name { font-size: 12px; color: #1d1d1f; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bubble { padding: 12px 16px; border-radius: 18px; font-size: 15px; line-height: 1.6; word-break: break-word; }
.bubble.user { background: #0071e3; color: #ffffff; border-bottom-right-radius: 4px; white-space: pre-wrap; overflow-wrap: break-word; }
.bubble.assistant { background: #ffffff; color: #1d1d1f; border: 1px solid rgba(0,0,0,0.06); border-bottom-left-radius: 4px; }
.bubble.assistant.stopped { border-color: rgba(255,149,0,0.25); }
.analyze-inline {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; color: #86868b; margin-bottom: 6px;
}
.ai-icon { display: flex; align-items: center; flex-shrink: 0; }
.ai-label { font-weight: 500; color: #1d1d1f; min-width: 28px; }
.ai-task { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.ai-status-icon { flex-shrink: 0; display: flex; align-items: center; }
.think { display: flex; align-items: center; gap: 4px; font-size: 12px; color: #86868b; cursor: pointer; margin-bottom: 6px; }
.think-text { font-size: 12px; color: #86868b; padding: 8px 12px; background: #f5f5f7; border-radius: 8px; margin-bottom: 8px; white-space: pre-wrap; line-height: 1.5; }
.memory-status { display: flex; align-items: center; gap: 4px; font-size: 12px; color: #8b5cf6; margin-bottom: 6px; }
.typing { display: flex; gap: 4px; }
.typing span { width: 6px; height: 6px; background: #0071e3; border-radius: 50%; animation: bounce 1.2s infinite; opacity: 0.5; }
.typing span:nth-child(2) { animation-delay: 0.2s; }
.typing span:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-4px)} }
.cursor { color: #0071e3; animation: blink 1s infinite; }
@keyframes blink { 0%,50%{opacity:1} 51%,100%{opacity:0} }
.actions { display: flex; align-items: center; gap: 6px; margin-top: 8px; opacity: 0; transition: opacity 0.2s; }
.assistant-block:hover .actions { opacity: 1; }
.actions button { display: inline-flex; align-items: center; gap: 3px; padding: 3px 10px; border: 1px solid rgba(0,0,0,0.08); border-radius: 10px; background: #ffffff; color: #86868b; cursor: pointer; font-size: 12px; font-family: inherit; }
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
.sugs { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.sugs button { padding: 5px 12px; border: 1px solid #0071e3; border-radius: 14px; background: transparent; color: #0071e3; cursor: pointer; font-size: 12px; font-family: inherit; }
.sugs button:hover { background: #0071e3; color: #ffffff; }
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
.input-row { display: flex; align-items: center;  gap: 6px; background: #ffffff; border: 1px solid rgba(0,0,0,0.08); border-radius: 28px; padding: 6px 8px 6px 14px; box-shadow: 0 2px 12px rgba(0,0,0,0.04); width: 100%; max-width: 640px; transition: border-color 0.2s, box-shadow 0.2s; }
.input-row:focus-within { border-color: rgba(0,113,227,0.3); box-shadow: 0 2px 16px rgba(0,113,227,0.08); }
.input-left { display: flex; align-items: center; gap: 2px; flex-shrink: 0; }
.model-switcher { position: relative; }
.model-btn { width: 32px; height: 32px; border: none; border-radius: 50%; background: transparent; color: #86868b; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.15s; }
.model-btn:hover { background: #f5f5f7; color: #1d1d1f; }
.model-btn.active { color: #0071e3; }
.model-menu { position: absolute; bottom: 44px; left: 0; width: 280px; background: #ffffff; border: 1px solid rgba(0,0,0,0.08); border-radius: 16px; padding: 6px; box-shadow: 0 8px 30px rgba(0,0,0,0.1); z-index: 100; }
.model-option { width: 100%; display: flex; align-items: center; justify-content: space-between; padding: 12px; border: none; border-radius: 12px; background: transparent; cursor: pointer; font-family: inherit; transition: background 0.15s; }
.model-option:hover { background: #f5f5f7; }
.model-option.selected { background: rgba(0,113,227,0.04); }
.option-left { display: flex; align-items: center; gap: 12px; }
.option-icon { width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; }
.option-icon.fast { background: rgba(255,193,7,0.15); color: #f59e0b; }
.option-icon.deep { background: rgba(139,92,246,0.15); color: #8b5cf6; }
.option-info { display: flex; flex-direction: column; text-align: left; }
.option-name { font-size: 14px; font-weight: 500; color: #1d1d1f; }
.option-desc { font-size: 12px; color: #86868b; margin-top: 1px; }
.popover-enter-active { transition: all 0.2s ease; }
.popover-leave-active { transition: all 0.15s ease; }
.popover-enter-from { opacity: 0; transform: translateY(6px) scale(0.96); }
.popover-leave-to { opacity: 0; transform: translateY(4px) scale(0.96); }
.input-btn { width: 32px; height: 32px; border: none; border-radius: 50%; background: transparent; color: #86868b; cursor: pointer; display: flex; align-items: center; justify-content: center; }
.input-btn:hover { color: #0071e3; }
.input-field { flex: 1; padding: 8px 0; border: none; background: transparent; font-size: 15px; font-family: inherit; color: #1d1d1f; outline: none; resize: none; min-height: 24px; max-height: 100px; line-height: 1.5; }
.input-field::placeholder { color: #b0b0b5; }
.send-btn { width: 32px; height: 32px; border: none; border-radius: 50%; background: #e5e5ea; color: #b0b0b5; cursor: pointer; display: flex; align-items: center; justify-content: center; flex-shrink: 0; transition: all 0.2s; }
.send-btn.active { background: #0071e3; color: #ffffff; }
.send-btn:disabled { cursor: not-allowed; }
.send-btn.stop { background: #ff3b30; color: #ffffff; animation: pulse 0.8s infinite; }
@keyframes pulse { 0%,100%{box-shadow:0 0 0 0 rgba(255,59,48,0.3)} 50%{box-shadow:0 0 0 8px rgba(255,59,48,0)} }
.input-hint { font-size: 11px; color: #b0b0b5; text-align: center; margin-top: 8px; }
.image-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.8); z-index: 1000; display: flex; align-items: center; justify-content: center; cursor: pointer; }
.image-overlay img { max-width: 90vw; max-height: 90vh; border-radius: 8px; object-fit: contain; }
.image-overlay-close { position: absolute; top: 20px; right: 20px; width: 40px; height: 40px; border: none; border-radius: 50%; background: rgba(255,255,255,0.15); color: #ffffff; cursor: pointer; display: flex; align-items: center; justify-content: center; }
.image-overlay-close:hover { background: rgba(255,255,255,0.25); }
</style>