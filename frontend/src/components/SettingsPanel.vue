<!--
文件名: src/components/SettingsPanel.vue
功能: 设置面板 - 通用/记忆/工具/模式（拖拽排序）+ API Key + 邮件配置 + 简化保存
-->
<template>
  <div class="settings">
    <div class="settings-sidebar">
      <button v-for="tab in tabs" :key="tab.key" class="tab-btn" :class="{ active: activeTab === tab.key }" @click="activeTab = tab.key">
        <component :is="tab.icon" :size="16" />
        <span>{{ tab.label }}</span>
      </button>
    </div>
    <div class="settings-content">
      <!-- 通用 -->
      <div v-if="activeTab === 'general'" class="tab-content">
        <h3>通用设置</h3>
        <div class="setting-row">
          <span>API Key</span>
          <input id="api-key-input" type="password" v-model="apiKey" placeholder="输入授权码" />
        </div>
        <p class="hint">用于验证软件使用权，由提供者分发</p>

        <div class="divider"></div>

        <h3 style="margin-top: 4px;">邮件配置</h3>
        <div class="setting-row">
          <span>发件人邮箱</span>
          <input v-model="settings.email.senderEmail" placeholder="your@qq.com" />
        </div>
        <div class="setting-row">
          <span>授权码</span>
          <input type="password" v-model="settings.email.authCode" placeholder="QQ邮箱授权码" />
        </div>
        <p class="hint">QQ邮箱 → 设置 → 账户 → POP3/SMTP 服务 → 生成授权码</p>
        <button class="test-btn" @click="testEmail" :disabled="!settings.email.senderEmail || !settings.email.authCode || testingEmail">
          {{ testingEmail ? '发送中...' : '发送测试邮件' }}
        </button>
      </div>

      <!-- 记忆 -->
      <div v-if="activeTab === 'memory'" class="tab-content">
        <h3>个人记忆</h3>
        <div class="setting-row">
          <span>启用个人记忆</span>
          <button class="toggle" :class="{ on: settings.memory.enabled }" @click="settings.memory.enabled = !settings.memory.enabled"></button>
        </div>
        <p class="hint">开启后 AI 会记住你的个人信息，在后续对话中运用</p>
        <div class="divider"></div>
        <div class="memory-header">
          <span>记忆列表 ({{ memories.length }})</span>
          <button class="danger-btn" @click="confirmClearMemories = true" :disabled="!memories.length">清空全部记忆</button>
        </div>
        <div class="memory-list" v-if="memories.length">
          <div v-for="(m, i) in memories" :key="i" class="memory-item">
            <Database :size="13" color="#8b5cf6" />
            <span>{{ m.content }}</span>
            <button class="memory-delete" @click="deleteMemory(i)"><X :size="12" /></button>
          </div>
        </div>
        <div v-else class="memory-empty">暂无记忆</div>
      </div>

      <!-- 工具 -->
      <div v-if="activeTab === 'tools'" class="tab-content">
        <h3>Agent 工具</h3>
        <p class="hint">控制 Agent 模式可用的工具</p>
        <div class="setting-row" v-for="t in toolList" :key="t.key">
          <span>{{ t.label }}</span>
          <button class="toggle" :class="{ on: settings.tools[t.key] }" @click="settings.tools[t.key] = !settings.tools[t.key]"></button>
        </div>
      </div>

      <!-- 模式 -->
      <div v-if="activeTab === 'modes'" class="tab-content">
        <h3>模式管理</h3>
        <p class="hint">拖拽调整顺序，关闭不需要的模式</p>
        <div class="mode-list" @dragover.prevent @drop="onDrop">
          <div v-for="(m, index) in modeList" :key="m.key" class="mode-item"
               draggable="true"
               @dragstart="onDragStart($event, index)"
               @dragenter.prevent="onDragEnter(index)"
               :class="{ 'drag-over': dragOverIndex === index }">
            <span class="mode-handle">⠿</span>
            <span class="mode-name">{{ m.label }}</span>
            <button class="toggle" :class="{ on: !settings.modes.disabled.includes(m.key) }" @click="toggleMode(m.key)"></button>
          </div>
        </div>
        <button class="reset-btn" style="margin-top:12px;" @click="resetModes">重置</button>
      </div>
    </div>

    <div class="settings-footer">
      <button class="reset-btn" @click="resetSettings">恢复默认</button>
      <button class="save-btn" @click="saveSettings">保存设置</button>
    </div>

    <!-- 清空记忆确认 -->
    <Modal :open="confirmClearMemories" title="清空记忆" width="360px" @close="confirmClearMemories = false">
      <p>确定要清空所有个人记忆吗？</p>
      <p style="color: #86868b; font-size: 13px;">此操作不可恢复</p>
      <template #footer>
        <button class="modal-btn cancel" @click="confirmClearMemories = false">取消</button>
        <button class="modal-btn danger" @click="doClearMemories">清空</button>
      </template>
    </Modal>

    <!-- 保存确认弹窗（iOS 风格底部 Sheet） -->
    <Teleport to="body">
      <Transition name="sheet">
        <div v-if="showSaveConfirm" class="sheet-overlay" @click.self="dismissSave">
          <div class="sheet-panel">
            <div class="sheet-bar"></div>
            <p class="sheet-title">保存修改？</p>
            <p class="sheet-desc">设置已修改，是否保存？</p>
            <div class="sheet-actions">
              <button class="sheet-btn secondary" @click="dismissSave">放弃</button>
              <button class="sheet-btn primary" @click="confirmSave">保存</button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, nextTick, inject } from 'vue'
import { Settings, Database, Wrench, Layers, X } from 'lucide-vue-next'
import Modal from '@/components/Modal.vue'

const toast = inject('toast', null)
const BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8765'

// 统一的 Toast 方法，优先用注入，失败则 dispatchEvent
function showToast(type, message, action) {
  try {
    if (toast?.value?.addToast) {
      toast.value.addToast(type, message, action)
      return
    }
  } catch {}
  window.dispatchEvent(new CustomEvent('toast', {
    detail: { type, message, action }
  }))
}

const tabs = [
  { key: 'general', label: '通用', icon: Settings },
  { key: 'memory', label: '记忆', icon: Database },
  { key: 'tools', label: '工具', icon: Wrench },
  { key: 'modes', label: '模式', icon: Layers },
]

const toolList = [
  { key: 'webSearch', label: '联网搜索' },
  { key: 'executeCode', label: '代码执行' },
  { key: 'calculate', label: '数学计算' },
  { key: 'getCurrentTime', label: '获取当前时间' },
]

const modeLabels = {
  normal: '日常模式', agent: 'Agent 模式', rag: '知识库 RAG',
  xray: '胸片诊断', email: '邮件模式', comingsoon: '敬请期待'
}

const activeTab = ref('general')
const apiKey = ref('')
const confirmClearMemories = ref(false)
const hasChanges = ref(false)
const showSaveConfirm = ref(false)
let pendingCloseCallback = null

const settings = reactive({
  memory: { enabled: true },
  email: { senderEmail: '', authCode: '' },
  tools: { webSearch: true, executeCode: true, calculate: true, getCurrentTime: true },
  modes: { order: ['normal', 'agent', 'rag', 'xray', 'email', 'comingsoon'], disabled: [] }
})

// 每次调用生成新默认值，避免引用共享
function getDefaultSettings() {
  return {
    memory: { enabled: true },
    email: { senderEmail: '', authCode: '' },
    tools: { webSearch: true, executeCode: true, calculate: true, getCurrentTime: true },
    modes: { order: ['normal', 'agent', 'rag', 'xray', 'email', 'comingsoon'], disabled: [] }
  }
}

const memories = ref([])
const testingEmail = ref(false)

const dragIndex = ref(-1)
const dragOverIndex = ref(-1)

const modeList = computed(() => {
  return settings.modes.order.map(key => ({ key, label: modeLabels[key] || key }))
})

watch(settings, () => { hasChanges.value = true }, { deep: true })
function markSaved() { hasChanges.value = false }

function onDragStart(e, index) { dragIndex.value = index; e.dataTransfer.effectAllowed = 'move' }
function onDragEnter(index) { dragOverIndex.value = index }
function onDrop() {
  if (dragIndex.value === -1 || dragOverIndex.value === -1) return
  const order = [...settings.modes.order]
  const item = order.splice(dragIndex.value, 1)[0]
  order.splice(dragOverIndex.value, 0, item)
  settings.modes.order = order
  dragIndex.value = -1; dragOverIndex.value = -1
}

function toggleMode(key) {
  const idx = settings.modes.disabled.indexOf(key)
  if (idx === -1) { settings.modes.disabled.push(key) }
  else { settings.modes.disabled.splice(idx, 1) }
}

function resetModes() {
  const def = getDefaultSettings()
  settings.modes.order = [...def.modes.order]
  settings.modes.disabled = [...def.modes.disabled]
}

async function loadSettings() {
  // 先关闭 hasChanges 监听，防止 Object.assign 触发
  hasChanges.value = false
  try {
    const res = await fetch(`${BASE}/settings`)
    const data = await res.json()
    // 只取需要的字段，避免后端残留字段污染 settings
    if (data.memory) Object.assign(settings.memory, data.memory)
    if (data.email) Object.assign(settings.email, data.email)
    if (data.tools) Object.assign(settings.tools, data.tools)
    if (data.modes) Object.assign(settings.modes, data.modes)
  } catch {}
  apiKey.value = localStorage.getItem('api_key') || ''
  // nextTick 确保 Object.assign 触发的 watch 回调已执行完毕
  nextTick(() => markSaved())
}

async function loadMemories() {
  try {
    const res = await fetch(`${BASE}/memory/list`)
    const data = await res.json()
    memories.value = data.memories || []
  } catch { memories.value = [] }
}

async function deleteMemory(idx) {
  const m = memories.value[idx]
  if (!m) return
  try {
    await fetch(`${BASE}/memory/${m.id || idx}`, { method: 'DELETE' })
    memories.value.splice(idx, 1)
    showToast('success', '已删除')
  } catch { showToast('error', '删除失败') }
}

async function doClearMemories() {
  try {
    await fetch(`${BASE}/memory`, { method: 'DELETE' })
    memories.value = []
    showToast('success', '记忆已清空')
  } catch { showToast('error', '清空失败') }
  confirmClearMemories.value = false
}

async function testEmail() {
  testingEmail.value = true
  try {
    const fd = new FormData()
    fd.append('smtp_host', 'smtp.qq.com')
    fd.append('smtp_port', '465')
    fd.append('sender_email', settings.email.senderEmail)
    fd.append('auth_code', settings.email.authCode)
    fd.append('test_recipient', settings.email.senderEmail)
    const res = await fetch(`${BASE}/settings/test-email`, { method: 'POST', body: fd })
    const data = await res.json()
    if (data.status === 'ok') { showToast('success', '测试邮件发送成功') }
    else { showToast('error', data.message || '发送失败') }
  } catch (e) { showToast('error', '请求失败') }
  testingEmail.value = false
}

async function saveSettings() {
  // 不管 apiKey 是否为空，都要同步更新 localStorage
  if (apiKey.value) {
    localStorage.setItem('api_key', apiKey.value)
  } else {
    localStorage.removeItem('api_key')
  }
  try {
    const fd = new FormData()
    fd.append('payload', JSON.stringify({ ...settings, apiKey: apiKey.value }))
    await fetch(`${BASE}/settings`, { method: 'POST', body: fd })
    markSaved()
    showToast('success', '设置已保存')
    window.dispatchEvent(new CustomEvent('settings-saved'))
  } catch { showToast('error', '保存失败') }
}

function resetSettings() {
  const def = getDefaultSettings()
  // 只重置以下内容，API Key 和邮件配置不重置
  settings.memory.enabled = def.memory.enabled
  settings.tools.webSearch = def.tools.webSearch
  settings.tools.executeCode = def.tools.executeCode
  settings.tools.calculate = def.tools.calculate
  settings.tools.getCurrentTime = def.tools.getCurrentTime
  settings.modes.order = [...def.modes.order]
  settings.modes.disabled = [...def.modes.disabled]
  showToast('info', '已恢复默认设置（API Key 和邮件配置未重置）')
}

// --- 保存确认逻辑 ---
function requestClose(callback) {
  if (hasChanges.value) {
    pendingCloseCallback = callback
    showSaveConfirm.value = true
  } else {
    callback()
  }
}

function dismissSave() {
  showSaveConfirm.value = false
  // 放弃保存，直接关闭面板，下次打开会从后端重新加载
  if (pendingCloseCallback) {
    pendingCloseCallback()
    pendingCloseCallback = null
  }
}

async function confirmSave() {
  showSaveConfirm.value = false
  await saveSettings()
  if (pendingCloseCallback) {
    pendingCloseCallback()
    pendingCloseCallback = null
  }
}

onMounted(() => {
  loadSettings()
  loadMemories()
  if (!apiKey.value) {
    activeTab.value = 'general'
    nextTick(() => {
      document.getElementById('api-key-input')?.focus()
    })
  }
})

watch(activeTab, (n) => { if (n === 'memory') loadMemories() })

defineExpose({ requestClose })
</script>

<style scoped>
.settings { display: flex; height: 420px; flex-direction: column; }
.settings-sidebar { display: flex; gap: 4px; padding: 8px 12px; border-bottom: 1px solid rgba(0,0,0,0.06); flex-shrink: 0; }
.tab-btn { display: flex; align-items: center; gap: 6px; padding: 8px 14px; border: none; border-radius: 8px; background: transparent; color: #86868b; cursor: pointer; font-size: 13px; font-family: inherit; }
.tab-btn:hover { background: rgba(0,0,0,0.04); color: #1d1d1f; }
.tab-btn.active { background: rgba(0,113,227,0.08); color: #0071e3; }
.settings-content { flex: 1; overflow-y: auto; padding: 16px 20px; }
.tab-content h3 { font-size: 15px; font-weight: 600; color: #1d1d1f; margin: 0 0 16px; }
.hint { font-size: 12px; color: #86868b; margin: 4px 0 12px; }
.setting-row { display: flex; align-items: center; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid rgba(0,0,0,0.04); }
.setting-row span { font-size: 14px; color: #1d1d1f; }
.setting-row input { width: 200px; padding: 6px 10px; border: 1px solid rgba(0,0,0,0.1); border-radius: 6px; font-size: 13px; color: #1d1d1f; outline: none; font-family: inherit; }
.setting-row input:focus { border-color: #0071e3; }
.toggle { width: 44px; height: 24px; border: none; border-radius: 12px; background: #e5e5ea; cursor: pointer; transition: background 0.2s; position: relative; }
.toggle::after { content: ''; position: absolute; top: 2px; left: 2px; width: 20px; height: 20px; border-radius: 50%; background: #fff; transition: transform 0.2s; box-shadow: 0 1px 3px rgba(0,0,0,0.2); }
.toggle.on { background: #34c759; }
.toggle.on::after { transform: translateX(20px); }
.divider { height: 1px; background: rgba(0,0,0,0.06); margin: 16px 0; }
.memory-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.memory-header span { font-size: 13px; color: #86868b; }
.danger-btn { padding: 5px 12px; border: 1px solid rgba(255,59,48,0.3); border-radius: 6px; background: transparent; color: #ff3b30; cursor: pointer; font-size: 12px; font-family: inherit; }
.danger-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.danger-btn:hover:not(:disabled) { background: rgba(255,59,48,0.08); }
.memory-list { display: flex; flex-direction: column; gap: 4px; max-height: 180px; overflow-y: auto; }
.memory-item { display: flex; align-items: center; gap: 8px; padding: 8px 10px; background: #f5f5f7; border-radius: 8px; font-size: 13px; color: #1d1d1f; }
.memory-item span { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.memory-delete { width: 24px; height: 24px; border: none; border-radius: 50%; background: transparent; color: #b0b0b5; cursor: pointer; display: flex; align-items: center; justify-content: center; }
.memory-delete:hover { background: rgba(255,59,48,0.1); color: #ff3b30; }
.memory-empty { font-size: 13px; color: #b0b0b5; text-align: center; padding: 20px; }
.mode-list { display: flex; flex-direction: column; }
.mode-item { display: flex; align-items: center; padding: 10px 0; border-bottom: 1px solid rgba(0,0,0,0.04); transition: background 0.15s; }
.mode-item.drag-over { background: rgba(0,113,227,0.05); border-radius: 8px; }
.mode-handle { cursor: grab; color: #b0b0b5; margin-right: 8px; font-size: 16px; user-select: none; }
.mode-handle:active { cursor: grabbing; }
.mode-name { flex: 1; font-size: 14px; color: #1d1d1f; }
.test-btn { padding: 8px 16px; border: 1px solid #0071e3; border-radius: 8px; background: transparent; color: #0071e3; cursor: pointer; font-size: 13px; font-family: inherit; margin-top: 12px; }
.test-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.test-btn:hover:not(:disabled) { background: rgba(0,113,227,0.08); }
.settings-footer { display: flex; align-items: center; justify-content: flex-end; gap: 12px; padding: 12px 20px; border-top: 1px solid rgba(0,0,0,0.06); flex-shrink: 0; }
.reset-btn { padding: 8px 16px; border: 1px solid rgba(0,0,0,0.08); border-radius: 8px; background: #fff; color: #86868b; cursor: pointer; font-size: 13px; font-family: inherit; }
.reset-btn:hover { border-color: #ff3b30; color: #ff3b30; }
.save-btn { padding: 8px 22px; border: none; border-radius: 8px; background: #0071e3; color: #fff; cursor: pointer; font-size: 13px; font-family: inherit; }
.save-btn:hover { background: #0077ed; }
.modal-btn { padding: 8px 18px; border: 1px solid rgba(0,0,0,0.08); border-radius: 8px; background: #fff; color: #1d1d1f; cursor: pointer; font-size: 13px; font-family: inherit; }
.modal-btn:hover { background: #f5f5f7; }
.modal-btn.danger { background: #ff3b30; border: none; color: #fff; }
.modal-btn.danger:hover { background: #e0352b; }

/* ===== iOS 风格底部 Sheet ===== */
.sheet-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.3);
  backdrop-filter: blur(4px); -webkit-backdrop-filter: blur(4px);
  z-index: 2000; display: flex; align-items: flex-end; justify-content: center;
}
.sheet-panel {
  width: 100%; max-width: 420px; background: #ffffff;
  border-radius: 16px 16px 0 0; padding: 16px 20px 28px;
  box-shadow: 0 -8px 32px rgba(0,0,0,0.1);
  animation: slideUp 0.25s ease;
}
@keyframes slideUp {
  from { transform: translateY(100%); }
  to { transform: translateY(0); }
}
.sheet-bar {
  width: 36px; height: 4px; background: #e0e0e0;
  border-radius: 2px; margin: 0 auto 16px;
}
.sheet-title {
  font-size: 17px; font-weight: 600; color: #1d1d1f;
  text-align: center; margin: 0 0 6px;
}
.sheet-desc {
  font-size: 14px; color: #86868b; text-align: center;
  margin: 0 0 20px;
}
.sheet-actions {
  display: flex; flex-direction: column; gap: 10px;
}
.sheet-btn {
  width: 100%; padding: 14px; border: none; border-radius: 12px;
  font-size: 16px; font-weight: 500; cursor: pointer;
  font-family: inherit; transition: all 0.15s;
}
.sheet-btn.primary {
  background: #0071e3; color: #ffffff;
}
.sheet-btn.primary:hover { background: #0077ed; }
.sheet-btn.secondary {
  background: #f5f5f7; color: #1d1d1f;
}
.sheet-btn.secondary:hover { background: #ebebed; }

/* Sheet 过渡动画 */
.sheet-enter-active { transition: opacity 0.25s ease; }
.sheet-leave-active { transition: opacity 0.2s ease; }
.sheet-enter-from, .sheet-leave-to { opacity: 0; }
</style>