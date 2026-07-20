<!--
文件名: src/components/AppShell.vue
功能: 主壳 - 模式排序/隐藏联动 + 删除确认弹窗 + 设置未保存确认（iOS Sheet）
-->
<template>
  <div class="shell">
    <header class="topbar">
      <div class="topbar-left">
        <span class="logo"><BrainCircuit :size="18" /></span>
        <span class="title">LocalMind</span>
        <span class="separator">·</span>
        <span class="mode-name">{{ currentMode?.name }}</span>
        <span class="conv-count" v-if="localConvs.length && modeStore.activeMode !== 'email'">{{ localConvs.length }} 个对话</span>
      </div>
      <div class="topbar-right"><button class="topbar-btn" title="设置" @click="openSettings"><Settings :size="15" /></button></div>
    </header>

    <div class="body">
      <nav class="mode-col">
        <button v-for="m in modes" :key="m.id" class="mode-btn" :class="{ active: modeStore.activeMode === m.id }" @click="switchMode(m.id)" :title="m.name"><component :is="m.icon" :size="20" /></button>
        <div class="mode-col-spacer"></div>
        <button class="mode-btn" title="设置" @click="openSettings"><Settings :size="20" /></button>
      </nav>

      <aside class="conv-col">
        <div class="conv-list">
          <template v-if="modeStore.activeMode === 'email'">
            <div class="conv-group">
              <div class="conv-group-label">已发送</div>
              <div v-if="emailSent.length===0" class="conv-empty">暂无已发送</div>
              <div v-for="(m,i) in emailSent" :key="'sent-'+i" class="conv-item" :class="{ active: activeSentIndex===i }" @click="viewSentMail(i)">
                <div class="conv-item-row">
                  <span class="conv-title">{{ m.to || '无收件人' }}</span>
                  <button class="conv-delete" @click.stop="confirmDeleteSent(m)" title="删除"><X :size="12" /></button>
                </div>
                <div class="conv-subtitle">{{ m.subject || '无主题' }}</div>
                <span class="conv-time">{{ fmtTimeFull(m.sentAt) }}</span>
                <span v-if="m.attachments?.length" class="conv-attachments">📎 {{ m.attachments.length }} 个附件</span>
              </div>
            </div>
            <div class="conv-group">
              <div class="conv-group-label">草稿箱 <span class="draft-count">{{ emailDrafts.length }}</span></div>
              <div v-if="emailDrafts.length===0" class="conv-empty">暂无草稿</div>
              <div v-for="d in emailDrafts" :key="d.id" class="conv-item draft-item" :class="{ active: activeDraftId===d.id && activeSentIndex===null }" @click="loadDraftToEditor(d)">
                <div class="conv-item-row"><span class="conv-title">{{ d.to || '无收件人' }}</span><button class="conv-delete" @click.stop="confirmDeleteDraft(d)" title="删除"><X :size="12" /></button></div>
                <div class="conv-subtitle">{{ d.subject || '无主题' }}</div>
                <span class="conv-time">{{ fmtTimeFull(d.updatedAt) }}</span>
              </div>
            </div>
          </template>
          <template v-else>
            <div v-if="todayList.length" class="conv-group"><div class="conv-group-label">今天</div><div v-for="c in todayList" :key="c.id" class="conv-item" :class="{ active: c.id===activeConvId }" @click="switchConv(c.id)"><div class="conv-item-row"><span class="conv-title">{{ c.title||'新对话' }}</span><button class="conv-delete" @click.stop="confirmDeleteConv(c)" title="删除"><X :size="12" /></button></div><span class="conv-time">{{ fmtTime(c.updated_at) }}</span></div></div>
            <div v-if="olderList.length" class="conv-group"><div class="conv-group-label">更早</div><div v-for="c in olderList" :key="c.id" class="conv-item" :class="{ active: c.id===activeConvId }" @click="switchConv(c.id)"><div class="conv-item-row"><span class="conv-title">{{ c.title||'新对话' }}</span><button class="conv-delete" @click.stop="confirmDeleteConv(c)" title="删除"><X :size="12" /></button></div><span class="conv-time">{{ fmtTime(c.updated_at) }}</span></div></div>
            <div v-if="!localConvs.length" class="conv-empty">暂无对话</div>
          </template>
        </div>
        <button class="conv-new" @click="createNew"><Plus :size="14" /> {{ modeStore.activeMode==='email'?'新建邮件':'新建' }}</button>
      </aside>

      <main class="workspace"><component :is="currentPage" :key="modeStore.activeMode" ref="workspaceRef" /></main>
    </div>

    <Modal :open="showSettings" title="设置" width="560px" @close="handleCloseSettings">
      <SettingsPanel ref="settingsRef" />
    </Modal>

    <Modal :open="!!deleteConvTarget" title="删除对话" @close="deleteConvTarget = null">
      <p>确定要删除「{{ deleteConvTarget?.title || '新对话' }}」吗？</p>
      <p style="color: #86868b; font-size: 13px;">删除后不可恢复</p>
      <template #footer>
        <button class="modal-btn cancel" @click="deleteConvTarget = null">取消</button>
        <button class="modal-btn danger" @click="doDeleteConv">删除</button>
      </template>
    </Modal>

    <Modal :open="!!deleteDraftTarget" title="删除草稿" @close="deleteDraftTarget = null">
      <p>确定要删除「{{ deleteDraftTarget?.subject || '无主题' }}」吗？</p>
      <p style="color: #86868b; font-size: 13px;">删除后不可恢复，关联的 AI 对话也会被删除</p>
      <template #footer>
        <button class="modal-btn cancel" @click="deleteDraftTarget = null">取消</button>
        <button class="modal-btn danger" @click="doDeleteDraft">删除</button>
      </template>
    </Modal>

    <Modal :open="!!deleteSentTarget" title="删除已发送" @close="deleteSentTarget = null">
      <p>确定要删除这条已发送记录吗？</p>
      <p style="color: #86868b; font-size: 13px;">仅删除本地记录，不会撤回邮件</p>
      <template #footer>
        <button class="modal-btn cancel" @click="deleteSentTarget = null">取消</button>
        <button class="modal-btn danger" @click="doDeleteSent">删除</button>
      </template>
    </Modal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, provide, inject } from 'vue'
import { defineAsyncComponent } from 'vue'
import { Settings, Plus, X, MessageCircle, Bot, Database, Scan, Mail, BrainCircuit, Sparkles } from 'lucide-vue-next'
import { useModeStore } from '@/stores/mode'
import { useChatStore } from '@/stores/chat'
import { ALL_MODES, MODE_ORDER } from '@/config/modes'
import Modal from '@/components/Modal.vue'
import SettingsPanel from '@/components/SettingsPanel.vue'
import ComingSoon from '@/pages/ComingSoon.vue'

const modeStore = useModeStore()
const chatStore = useChatStore()
const toast = inject('toast')
const showSettings = ref(false)
const settingsRef = ref(null)
const activeConvId = ref(null)
const activeDraftId = ref(null)
const activeSentIndex = ref(null)
const workspaceRef = ref(null)

const BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8765'
const emailDrafts = ref([])
const emailSent = ref([])
const deleteConvTarget = ref(null)
const deleteDraftTarget = ref(null)
const deleteSentTarget = ref(null)

// ========== 模式排序与隐藏 ==========
const modeOrder = ref([...MODE_ORDER])
const disabledModes = ref([])

async function loadModeConfig() {
  try {
    const res = await fetch(`${BASE}/settings`)
    const data = await res.json()
    if (data.modes?.order) modeOrder.value = data.modes.order
    if (data.modes?.disabled) disabledModes.value = data.modes.disabled
  } catch {}
}

const iconMap = { MessageCircle, Bot, Database, Scan, Mail, Sparkles }
const allModeDefs = { ...ALL_MODES, comingsoon: { id: 'comingsoon', name: '敬请期待', icon: 'Sparkles' } }
const modes = computed(() => {
  return modeOrder.value
    .filter(id => !disabledModes.value.includes(id))
    .map(id => ({ id, ...allModeDefs[id], icon: iconMap[allModeDefs[id].icon] }))
})

function onSettingsSaved() { loadModeConfig() }

onMounted(() => {
  window.addEventListener('settings-saved', onSettingsSaved)
  window.addEventListener('open-settings', openSettings)
  loadModeConfig()
})
onUnmounted(() => {
  window.removeEventListener('settings-saved', onSettingsSaved)
  window.removeEventListener('open-settings', openSettings)
})

function openSettings() { showSettings.value = true }

function handleCloseSettings() {
  if (settingsRef.value?.requestClose) {
    settingsRef.value.requestClose(() => { showSettings.value = false })
  } else {
    showSettings.value = false
  }
}

const currentMode = computed(() => allModeDefs[modeStore.activeMode])

const NormalPage = defineAsyncComponent(() => import('@/pages/NormalPage.vue'))
const AgentPage = defineAsyncComponent(() => import('@/pages/AgentPage.vue'))
const RAGPage = defineAsyncComponent(() => import('@/pages/RAGPage.vue'))
const XRayPage = defineAsyncComponent(() => import('@/pages/XRayPage.vue'))
const EmailPage = defineAsyncComponent(() => import('@/pages/EmailPage.vue'))
const pageMap = { normal: NormalPage, agent: AgentPage, rag: RAGPage, xray: XRayPage, email: EmailPage, comingsoon: ComingSoon }
const currentPage = computed(() => pageMap[modeStore.activeMode] || ComingSoon)

const localConvs = computed(() => chatStore.conversations)
function isToday(s) { return s ? new Date(s).toDateString() === new Date().toDateString() : false }
const todayList = computed(() => localConvs.value.filter(c => isToday(c.updated_at)))
const olderList = computed(() => localConvs.value.filter(c => !isToday(c.updated_at)))

function fmtTime(ts) {
  if (!ts) return ''
  const d = new Date(ts), now = new Date(), diff = now - d
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
  if (d.toDateString() === now.toDateString()) return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function fmtTimeFull(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`
}

async function loadEmailData() {
  try {
    const [d, s] = await Promise.all([
      fetch(`${BASE}/email/drafts`).then(r => r.json()),
      fetch(`${BASE}/email/sent`).then(r => r.json()),
    ])
    emailDrafts.value = d.drafts || []
    emailSent.value = s.sent || []
  } catch { emailDrafts.value = []; emailSent.value = [] }
}

function confirmDeleteConv(c) { deleteConvTarget.value = { id: c.id, title: c.title } }
async function doDeleteConv() {
  if (!deleteConvTarget.value) return
  try {
    await chatStore.deleteConversation(deleteConvTarget.value.id)
    if (activeConvId.value === deleteConvTarget.value.id) activeConvId.value = null
    toast.value.success('对话已删除')
  } catch (e) { toast.value.error('删除失败') }
  finally { deleteConvTarget.value = null }
}

function confirmDeleteDraft(d) { deleteDraftTarget.value = d }
async function doDeleteDraft() {
  const d = deleteDraftTarget.value
  if (!d) return
  try {
    let convId = null
    try {
      const r = await fetch(`${BASE}/email/drafts/${d.id}`)
      const data = await r.json()
      convId = data.mail?.convId
    } catch {}
    await fetch(`${BASE}/email/drafts/${d.id}`, { method: 'DELETE' })
    if (convId) { await fetch(`${BASE}/chat/conversations/${convId}`, { method: 'DELETE' }).catch(() => {}) }
    if (activeDraftId.value === d.id) {
      activeDraftId.value = null
      if (workspaceRef.value?.newMail) workspaceRef.value.newMail()
    }
    toast.value.success('草稿已删除')
  } catch (e) { toast.value.error('删除失败') }
  finally {
    deleteDraftTarget.value = null
    await loadEmailData()
  }
}

function confirmDeleteSent(m) { deleteSentTarget.value = m }
async function doDeleteSent() {
  const m = deleteSentTarget.value
  if (!m) return
  try {
    await fetch(`${BASE}/email/sent/${m.id}`, { method: 'DELETE' })
    if (activeSentIndex.value !== null && emailSent.value[activeSentIndex.value]?.id === m.id) {
      activeSentIndex.value = null
      if (workspaceRef.value?.newMail) workspaceRef.value.newMail()
    }
    toast.value.success('已删除')
  } catch (e) { toast.value.error('删除失败') }
  finally {
    deleteSentTarget.value = null
    await loadEmailData()
  }
}

async function loadDraftToEditor(draft) {
  activeDraftId.value = draft.id; activeSentIndex.value = null
  try {
    const r = await fetch(`${BASE}/email/drafts/${draft.id}`)
    const data = await r.json()
    if (workspaceRef.value?.loadDraft) workspaceRef.value.loadDraft({ ...draft, body: data.mail?.body || draft.body })
  } catch { if (workspaceRef.value?.loadDraft) workspaceRef.value.loadDraft(draft) }
}

function viewSentMail(index) {
  activeSentIndex.value = index; activeDraftId.value = null
  const m = emailSent.value[index]
  if (m && workspaceRef.value?.viewSent) workspaceRef.value.viewSent(m)
}

function handleDraftUpdate() { loadEmailData() }
provide('refreshDrafts', handleDraftUpdate)

async function loadConvs() { await chatStore.loadConversations(modeStore.activeMode) }
async function switchConv(convId) { activeConvId.value = convId; await chatStore.switchConversation(convId) }

async function createNew() {
  if (modeStore.activeMode === 'email') {
    if (workspaceRef.value?.checkLeave) {
      const canLeave = await workspaceRef.value.checkLeave()
      if (!canLeave) return
    }
    activeDraftId.value = null
    activeSentIndex.value = null
    if (workspaceRef.value?.newMail) workspaceRef.value.newMail()
  } else {
    activeConvId.value = null
    await chatStore.createConversation(modeStore.activeMode)
  }
}

async function switchMode(mode) {
  if (mode === modeStore.activeMode) return
  if (mode === 'comingsoon') {
    modeStore.switchMode(mode)
    chatStore.conversations = []
    return
  }
  if (modeStore.activeMode === 'email' && workspaceRef.value?.checkLeave) {
    const canLeave = await workspaceRef.value.checkLeave()
    if (!canLeave) return
  }
  // 停止前先给当前对话追加停止提示
  if (chatStore.messages.length > 0) {
    const last = chatStore.messages[chatStore.messages.length - 1]
    if (last.role === 'assistant' && last.isStreaming) {
      last.isStreaming = false
      last.stopped = true
    }
  }
  chatStore.stopGeneration()
  chatStore.beforeModeSwitch()
  // 立即清空视图，避免闪现旧对话和残留步骤
  chatStore.messages = []
  chatStore.agentSteps = []
  chatStore.xrayResults = null
  chatStore.xrayProgress = null
  await fetch(`${BASE}/chat/mode/switch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ mode })
  })
  modeStore.switchMode(mode)
  activeConvId.value = null; activeDraftId.value = null; activeSentIndex.value = null
  await chatStore.afterModeSwitch(mode)
  if (mode === 'email') loadEmailData()
}

onMounted(async () => {
  chatStore.setupBeforeUnload()
  chatStore.messages = []
  chatStore.agentSteps = []
  chatStore.xrayResults = null
  chatStore.xrayProgress = null
  chatStore.xrayReports = {}
  await loadConvs()
  loadEmailData()
  await chatStore.afterModeSwitch(modeStore.activeMode)
})
watch(() => modeStore.activeMode, (n) => { if (n === 'email') loadEmailData() })
</script>

<style scoped>
.shell { display: flex; flex-direction: column; height: 100vh; background: #f5f5f7; }
.topbar { height: 44px; display: flex; align-items: center; justify-content: space-between; padding: 0 16px; background: rgba(245,245,247,0.72); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); border-bottom: 1px solid rgba(0,0,0,0.06); z-index: 10; flex-shrink: 0; }
.topbar-left { display: flex; align-items: center; gap: 8px; min-width: 0; }
.logo { display: flex; align-items: center; justify-content: center; color: #0071e3; }
.title { font-size: 14px; font-weight: 600; color: #1d1d1f; }
.separator { color: #ccc; }
.mode-name { font-size: 13px; color: #86868b; }
.conv-count { font-size: 12px; color: #b0b0b5; }
.topbar-right { display: flex; align-items: center; gap: 6px; }
.topbar-btn { width: 28px; height: 28px; border: none; border-radius: 6px; background: transparent; color: #86868b; cursor: pointer; display: flex; align-items: center; justify-content: center; }
.topbar-btn:hover { background: rgba(0,0,0,0.05); color: #1d1d1f; }
.body { flex: 1; display: flex; overflow: hidden; }
.mode-col { width: 48px; display: flex; flex-direction: column; align-items: center; padding: 8px 0; background: #f0f0f3; border-right: 1px solid rgba(0,0,0,0.06); gap: 2px; flex-shrink: 0; }
.mode-btn { width: 36px; height: 36px; border: none; border-radius: 8px; background: transparent; color: #86868b; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.15s; }
.mode-btn:hover { background: rgba(0,0,0,0.05); color: #1d1d1f; }
.mode-btn.active { background: rgba(0,113,227,0.1); color: #0071e3; }
.mode-col-spacer { flex: 1; }
.conv-col { width: 220px; display: flex; flex-direction: column; background: #f0f0f3; border-right: 1px solid rgba(0,0,0,0.06); flex-shrink: 0; }
.conv-list { flex: 1; overflow-y: auto; padding: 8px; }
.conv-group { margin-bottom: 12px; }
.conv-group-label { font-size: 11px; font-weight: 600; color: #86868b; padding: 4px 8px; text-transform: uppercase; letter-spacing: 0.3px; display: flex; align-items: center; gap: 6px; }
.draft-count { font-size: 10px; font-weight: 500; background: rgba(255,149,0,0.15); color: #ff9500; padding: 1px 6px; border-radius: 8px; }
.conv-item { padding: 8px; border-radius: 8px; cursor: pointer; transition: background 0.15s; }
.conv-item:hover { background: rgba(0,0,0,0.04); }
.conv-item.active { background: rgba(0,113,227,0.08); }
.draft-item.active { background: rgba(255,149,0,0.08); }
.conv-item-row { display: flex; align-items: center; justify-content: space-between; gap: 4px; }
.conv-title { font-size: 13px; color: #1d1d1f; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.conv-subtitle { font-size: 11px; color: #86868b; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-top: 1px; }
.conv-delete { width: 24px; height: 24px; border: none; border-radius: 4px; background: transparent; color: #b0b0b5; cursor: pointer; display: flex; align-items: center; justify-content: center; flex-shrink: 0; transition: all 0.15s; opacity: 0.4; }
.conv-item:hover .conv-delete { opacity: 1; color: #86868b; }
.conv-delete:hover { background: rgba(0,0,0,0.08); color: #d93e34 !important; }
.conv-time { font-size: 11px; color: #b0b0b5; margin-top: 2px; display: block; }
.conv-attachments { font-size: 10px; color: #b0b0b5; display: block; margin-top: 1px; }
.conv-empty { font-size: 13px; color: #b0b0b5; padding: 12px 8px; text-align: center; }
.conv-new { display: flex; align-items: center; justify-content: center; gap: 6px; padding: 10px; margin: 8px; border: 1px solid rgba(0,0,0,0.08); border-radius: 10px; background: #fff; color: #0071e3; cursor: pointer; font-size: 13px; font-family: inherit; transition: all 0.15s; }
.conv-new:hover { background: #f5f5f7; }
.workspace { flex: 1; overflow: hidden; background: #fff; }

.modal-btn { padding: 8px 18px; border: 1px solid rgba(0,0,0,0.08); border-radius: 8px; background: #fff; color: #1d1d1f; cursor: pointer; font-size: 13px; font-family: inherit; }
.modal-btn:hover { background: #f5f5f7; }
.modal-btn.danger { background: #ff3b30; border: none; color: #fff; }
.modal-btn.danger:hover { background: #e0352b; }
</style>