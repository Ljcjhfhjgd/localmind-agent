<!--
文件名: src/pages/XRayPage.vue
功能: 胸片诊断模式 - 支持 **加粗** 渲染
-->
<template>
  <div class="xray-page">
    <div v-if="pageState === 'restoring'" class="xray-loading">
      <div class="loading-spinner"></div>
      <p>恢复对话中...</p>
    </div>

    <div v-if="pageState === 'empty'" class="xray-empty">
      <div class="empty-icon"><Scan :size="48" color="#0071e3" /></div>
      <h2>胸片诊断</h2>
      <p>上传胸部 X 光片，AI 辅助识别 20 种常见疾病</p>
      <div class="upload-zone" @dragover.prevent="dragOver = true" @dragleave.prevent="dragOver = false" @drop.prevent="onDrop" @click="triggerUpload" :class="{ over: dragOver }">
        <Upload :size="28" /><span>点击或拖拽上传胸片</span><span class="upload-hint">支持 JPG、PNG，可一次选择多张</span>
      </div>
      <input ref="fileInput" type="file" hidden accept="image/*" multiple @change="onFileSelect" />
    </div>

    <div v-if="pageState === 'analyzing'" class="xray-loading">
      <div class="loading-spinner"></div>
      <p>分析中...共 {{ totalCount }} 张胸片</p>
      <div v-if="xrayProgress" class="progress-info">已完成 {{ xrayProgress.current }}/{{ xrayProgress.total }}</div>
    </div>

    <div v-if="pageState === 'rejected'" class="xray-empty">
      <div class="empty-icon"><AlertCircle :size="48" color="#f59e0b" /></div>
      <h2>非胸片图像</h2><p>{{ rejectedMsg }}</p>
      <div class="btn-group">
        <button class="btn-new" @click="resetToEmpty">重新上传</button>
        <button v-if="canRetry" class="btn-retry" @click="retryLastImage"><RefreshCw :size="14" /> 重新检测</button>
      </div>
    </div>

    <div v-if="pageState === 'error'" class="xray-empty">
      <div class="empty-icon"><AlertCircle :size="48" color="#ff3b30" /></div>
      <h2>诊断出错</h2><p>{{ errorMsg }}</p>
      <button class="btn-new" @click="resetToEmpty">重新上传</button>
    </div>

    <div v-if="pageState === 'result'" class="xray-result-layout">
      <aside class="xray-sidebar">
        <button class="btn-new sidebar-upload-btn" @click="resetToEmpty"><Upload :size="14" /> 重新上传</button>
        <div class="thumb-list">
          <div v-for="(item, i) in allResults" :key="i" class="thumb-card" :class="{ active: selectedIndex === i }" @click="selectImage(i)">
            <div class="thumb-img-wrap">
              <img v-if="getThumbUrl(item.file_name)" :src="getThumbUrl(item.file_name)" />
              <Image v-else :size="36" />
              <div class="thumb-status-icon"><CheckCircle v-if="item.status === 'ok'" :size="16" color="#34c759" /><AlertCircle v-else-if="item.status === 'rejected'" :size="16" color="#f59e0b" /><XCircle v-else :size="16" color="#ff3b30" /></div>
            </div>
            <span class="thumb-name">{{ item.file_name }}</span>
          </div>
        </div>
      </aside>

      <main class="xray-main" v-if="currentResult">
        <div class="result-card">
          <div class="result-image" @click="showFullImage = true"><img :src="getThumbUrl(currentResult.file_name)" alt="胸片" /><div class="image-overlay-hint"><Maximize2 :size="16" /></div></div>
          <div class="result-info">
            <div class="file-name"><Image :size="16" /><span>{{ currentResult.file_name }}</span></div>
            <template v-if="currentResult.status === 'ok'">
              <div class="verdict-badge" :class="verdictClass">{{ verdictIcon }} {{ currentResult.category || '分析完成' }}</div>
              <div class="verdict-reason">{{ currentResult.reason }}</div>
            </template>
            <template v-else-if="currentResult.status === 'rejected'">
              <div class="verdict-badge verdict-rejected"><AlertCircle :size="18" /> 非胸片图像</div>
              <div class="verdict-reason">{{ currentResult.reason }}</div>
              <button class="btn-retry" @click="retrySingleImage(currentResult.file_name)" :disabled="retrying"><RefreshCw :size="14" :class="{ spin: retrying }" />{{ retrying ? '检测中...' : '重新检测' }}</button>
            </template>
            <template v-else>
              <div class="verdict-badge verdict-danger"><XCircle :size="18" /> 诊断失败</div>
              <div class="verdict-reason">{{ currentResult.reason }}</div>
              <button class="btn-retry" @click="retrySingleImage(currentResult.file_name)" :disabled="retrying"><RefreshCw :size="14" :class="{ spin: retrying }" />{{ retrying ? '重试中...' : '重新检测' }}</button>
            </template>
          </div>
        </div>

        <div v-if="currentResult.status === 'ok'" class="result-columns">
          <div class="column prob-column">
            <div class="column-title"><Activity :size="16" /> 疾病概率</div>
            <div class="prob-list">
              <div v-for="item in probItems" :key="item.name" class="prob-row">
                <div class="prob-header"><span class="prob-name">{{ item.name }}</span><span class="prob-value" :class="probColorClass(item.prob, item.isNormal)">{{ item.prob }}%</span></div>
                <div class="prob-bar"><div class="prob-fill" :style="{ width: Math.min(item.prob, 100) + '%' }" :class="probBarClass(item.prob, item.isNormal)"></div></div>
              </div>
            </div>
          </div>
          <div class="column report-column">
            <div class="column-title"><FileText :size="16" /> AI 诊断报告</div>
            <div v-if="currentReportContent" class="report-text" v-html="mdReport(currentReportContent)"></div>
            <div v-else-if="currentReportLoading" class="report-loading"><Loader :size="20" class="spin" /><span>正在生成报告...</span></div>
            <div v-else class="report-loading"><span>点击缩略图以生成 AI 诊断报告</span></div>
          </div>
        </div>

        <div class="disclaimer"><AlertCircle :size="13" />本诊断由 AI 生成，仅供参考，不能替代专业医师意见。</div>
      </main>
    </div>

    <Teleport to="body">
      <div v-if="showFullImage && currentResult" class="full-image-overlay" @click="showFullImage = false"><img :src="getThumbUrl(currentResult.file_name)" /><button class="close-btn" @click="showFullImage = false"><X :size="20" /></button></div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { Scan, Upload, AlertCircle, X, RefreshCw, Image, Activity, FileText, Maximize2, CheckCircle, XCircle, Loader } from 'lucide-vue-next'
import { useChatStore } from '@/stores/chat'

const chatStore = useChatStore()
const pageState = ref('restoring')
const loadingStep = ref('')
const rejectedMsg = ref('')
const canRetry = ref(false)
const errorMsg = ref('')
const showFullImage = ref(false)
const dragOver = ref(false)
const selectedIndex = ref(-1)
const retrying = ref(false)
const fileInput = ref(null)
const lastFile = ref(null)
const uploadPreviews = ref([])
let checkTimer = null

const xrayProgress = computed(() => chatStore.xrayProgress)
const allResults = computed(() => chatStore.xrayResults || [])
const totalCount = computed(() => chatStore.xrayProgress?.total || uploadPreviews.value.length || 0)
const currentResult = computed(() => { const r = allResults.value; if (!r.length) return null; return r[Math.max(0, Math.min(selectedIndex.value, r.length - 1))] || r[0] })
const currentReportContent = computed(() => { if (!currentResult.value) return ''; const r = chatStore.xrayReports[currentResult.value.file_name]; return r?.content || '' })
const currentReportLoading = computed(() => { if (!currentResult.value) return false; const r = chatStore.xrayReports[currentResult.value.file_name]; return r?.loading || false })
const lastRejectedMsg = computed(() => [...chatStore.messages].reverse().find(m => m.role === 'assistant' && m.xrayRejected) || null)
const lastErrorMsg = computed(() => [...chatStore.messages].reverse().find(m => m.role === 'assistant' && m.xrayError) || null)
const userImageMsg = computed(() => [...chatStore.messages].reverse().find(m => m.role === 'user' && m.files?.length) || null)
function getThumbUrl(n) { if (!userImageMsg.value?.files) return null; const f = userImageMsg.value.files.find(x => x.name === n); return f?.url || f?.thumb || null }
const verdictText = computed(() => currentResult.value?.category || '')
const verdictClass = computed(() => ({ '正常': 'verdict-normal', '建议复查': 'verdict-warn', '异常': 'verdict-danger' })[verdictText.value] || 'verdict-normal')
const verdictIcon = computed(() => ({ '正常': '✅', '建议复查': '⚠️', '异常': '❌' })[verdictText.value] || '')
const probItems = computed(() => {
  const d = currentResult.value?.all_probs; if (!d) return []
  const list = []
  if (d.no_finding_prob > 0) list.push({ name: '未见异常（正常）', prob: Math.round(d.no_finding_prob), isNormal: true })
  if (d.diseases) for (const x of d.diseases) { if (x.probability > 0) list.push({ name: x.disease_cn, prob: Math.round(x.probability), isNormal: false }) }
  return list
})
function probColorClass(p, n) { if (n) return 'prob-green'; if (p > 50) return 'prob-red'; return 'prob-orange' }
function probBarClass(p, n) { if (n) return 'bar-green'; if (p > 50) return 'bar-red'; return 'bar-orange' }

// 报告渲染：支持 **加粗**
function mdReport(c) {
  if (!c) return ''
  return c.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br>')
}

function selectImage(i) {
  selectedIndex.value = i
  const r = allResults.value[i]
  if (r?.status === 'ok' && r.file_name) {
    const rep = chatStore.xrayReports[r.file_name]
    if (!rep?.loading) chatStore.generateXrayReport(r.file_name)
  }
}

function syncStateFromMessages() {
  const msgs = chatStore.messages
  if (!msgs.length) { pageState.value = 'empty'; return }
  if (userImageMsg.value?.files) uploadPreviews.value = userImageMsg.value.files.map(f => ({ name: f.name, thumb: f.thumb || f.url }))
  if (chatStore.xrayResults?.length && selectedIndex.value < 0) {
    selectedIndex.value = 0
    const firstOk = chatStore.xrayResults.find(r => r.status === 'ok')
    if (firstOk && !chatStore.xrayReports[firstOk.file_name]?.content && !chatStore.xrayReports[firstOk.file_name]?.loading) setTimeout(() => chatStore.generateXrayReport(firstOk.file_name), 800)
  }
  if (lastRejectedMsg.value && !chatStore.xrayResults?.length) { rejectedMsg.value = lastRejectedMsg.value.xrayRejected?.reason || '请上传胸部X光片'; canRetry.value = lastRejectedMsg.value.xrayRejected?.retry_allowed ?? true; pageState.value = 'rejected'; return }
  if (lastErrorMsg.value && !chatStore.xrayResults?.length) { errorMsg.value = lastErrorMsg.value.xrayError?.message || '诊断出错'; pageState.value = 'error'; return }
  if (chatStore.xrayResults?.length) { pageState.value = 'result'; return }
  const last = msgs[msgs.length - 1]
  if (last?.role === 'assistant' && last.isStreaming) { pageState.value = 'analyzing'; startPolling(); return }
  pageState.value = 'empty'
}

function startPolling() {
  if (checkTimer) clearInterval(checkTimer)
  checkTimer = setInterval(() => {
    if (chatStore.xrayResults?.length) { clearInterval(checkTimer); checkTimer = null; pageState.value = 'result'; if (selectedIndex.value < 0) { selectedIndex.value = 0; const f = chatStore.xrayResults.find(r => r.status === 'ok'); if (f && !chatStore.xrayReports[f.file_name]?.content && !chatStore.xrayReports[f.file_name]?.loading) setTimeout(() => chatStore.generateXrayReport(f.file_name), 800) } return }
    const last = chatStore.messages[chatStore.messages.length - 1]
    if (last?.xrayRejected && !chatStore.xrayResults?.length) { clearInterval(checkTimer); checkTimer = null; rejectedMsg.value = last.xrayRejected.reason || ''; canRetry.value = last.xrayRejected.retry_allowed ?? true; pageState.value = 'rejected'; return }
    if (last?.xrayError) { clearInterval(checkTimer); checkTimer = null; errorMsg.value = last.xrayError.message || ''; pageState.value = 'error'; return }
    if (!last || last.role !== 'assistant') return
    if (last.isStreaming === false && !chatStore.xrayResults?.length && !last.xrayRejected) { clearInterval(checkTimer); checkTimer = null; const c = last.content || ''; if (c.includes('非胸片') || c.includes('不是胸片')) { rejectedMsg.value = c; canRetry.value = true; pageState.value = 'rejected' } else if (c) { pageState.value = 'result' } else { pageState.value = 'empty' } }
  }, 300)
}

function triggerUpload() { fileInput.value?.click() }
function onFileSelect(e) { if (e.target.files.length) addFiles(e.target.files); e.target.value = '' }
function onDrop(e) { dragOver.value = false; if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files) }
function addFiles(fl) {
  const files = []; for (const f of fl) { if (!f.type.startsWith('image/')) continue; files.push(f); uploadPreviews.value.push({ name: f.name, thumb: URL.createObjectURL(f) }) }
  if (!files.length) { rejectedMsg.value = '请上传图片文件'; pageState.value = 'rejected'; return }
  lastFile.value = files; selectedIndex.value = -1; startDiagnose(files)
}
async function startDiagnose(files) {
  if (checkTimer) clearInterval(checkTimer)
  chatStore.createConversation('xray'); await nextTick(); loadingStep.value = '正在进行 AI 验证...'
  chatStore.sendMessage('', files.map(f => ({ name: f.name, type: 'image', file: f, thumb: uploadPreviews.value.find(p => p.name === f.name)?.thumb || null, url: uploadPreviews.value.find(p => p.name === f.name)?.thumb || null })), false, 'xray')
  startPolling()
}
function retryLastImage() { if (!lastFile.value) return; pageState.value = 'analyzing'; selectedIndex.value = -1; startDiagnose(Array.isArray(lastFile.value) ? lastFile.value : [lastFile.value]) }
async function retrySingleImage(fn) {
  const cid = chatStore.currentModeConvId; if (!cid || retrying.value) return
  retrying.value = true
  try { await chatStore.retrySingleXray(cid, fn); const r = chatStore.xrayResults; if (r) { const u = r.find(x => x.file_name === fn); if (u) { selectedIndex.value = r.indexOf(u); if (u.status === 'ok') setTimeout(() => chatStore.generateXrayReport(fn), 500) } } } catch (e) { console.error(e) } finally { retrying.value = false }
}
function resetToEmpty() { if (checkTimer) clearInterval(checkTimer); const cid = chatStore.currentModeConvId; if (cid) chatStore.deleteConversation(cid); else chatStore.createConversation('xray'); pageState.value = 'empty'; lastFile.value = null; uploadPreviews.value = []; loadingStep.value = ''; rejectedMsg.value = ''; canRetry.value = false; errorMsg.value = ''; selectedIndex.value = -1 }
function nextTick() { return new Promise(r => setTimeout(r, 0)) }

onMounted(async () => {
  pageState.value = 'restoring'; selectedIndex.value = -1
  try { await chatStore.loadConversations('xray'); if (chatStore.messages.length > 0) { syncStateFromMessages(); return }; const ok = await chatStore.restoreLastConversation('xray'); if (ok) syncStateFromMessages() } catch (e) { console.error(e) } finally { if (pageState.value === 'restoring') pageState.value = 'empty' }
})
onUnmounted(() => { if (checkTimer) clearInterval(checkTimer) })
watch(() => chatStore.messages, () => { if (pageState.value === 'analyzing') return; syncStateFromMessages() }, { deep: true })
watch(() => chatStore.currentModeConvId, () => { lastFile.value = null; uploadPreviews.value = []; loadingStep.value = ''; selectedIndex.value = -1; syncStateFromMessages() })
</script>

<style scoped>
.xray-page { height: 100%; display: flex; flex-direction: column; background: #f5f5f7; overflow: hidden; }
.xray-loading { display: flex; flex-direction: column; align-items: center; justify-content: center; flex: 1; gap: 16px; }
.loading-spinner { width: 40px; height: 40px; border: 3px solid #e5e5ea; border-top-color: #0071e3; border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.xray-loading p { font-size: 16px; font-weight: 500; color: #1d1d1f; margin: 0; }
.loading-step { font-size: 13px; color: #86868b; }
.progress-info { font-size: 14px; color: #0071e3; font-weight: 500; }
.xray-empty { display: flex; flex-direction: column; align-items: center; justify-content: center; flex: 1; gap: 12px; text-align: center; }
.empty-icon { margin-bottom: 8px; }
.xray-empty h2 { font-size: 20px; font-weight: 600; color: #1d1d1f; margin: 0; }
.xray-empty p { font-size: 14px; color: #86868b; margin: 0; max-width: 400px; line-height: 1.5; }
.upload-zone { width: 320px; padding: 32px; border: 2px dashed rgba(0,0,0,0.1); border-radius: 16px; cursor: pointer; transition: all 0.2s; display: flex; flex-direction: column; align-items: center; gap: 8px; color: #86868b; margin-top: 16px; }
.upload-zone:hover, .upload-zone.over { border-color: #0071e3; background: rgba(0,113,227,0.03); color: #0071e3; }
.upload-hint { font-size: 12px !important; color: #b0b0b5 !important; }
.btn-group { display: flex; gap: 12px; margin-top: 8px; }
.btn-new { padding: 10px 24px; border: 1px solid #0071e3; border-radius: 10px; background: transparent; color: #0071e3; cursor: pointer; font-size: 14px; font-weight: 500; transition: all 0.15s; display: flex; align-items: center; gap: 6px; }
.btn-new:hover { background: #0071e3; color: #fff; }
.btn-retry { padding: 10px 24px; border: 1px solid #f59e0b; border-radius: 10px; background: transparent; color: #f59e0b; cursor: pointer; font-size: 14px; font-weight: 500; display: flex; align-items: center; gap: 6px; transition: all 0.15s; }
.btn-retry:hover { background: #f59e0b; color: #fff; }
.btn-retry:disabled { opacity: 0.5; cursor: not-allowed; }
.spin { animation: spin 1s linear infinite; }
.sidebar-upload-btn { margin: 8px; width: calc(100% - 16px); justify-content: center; }
.xray-result-layout { display: flex; height: 100%; overflow: hidden; }
.xray-sidebar { width: 200px; flex-shrink: 0; background: #f0f0f3; border-right: 1px solid rgba(0,0,0,0.06); display: flex; flex-direction: column; overflow-y: auto; }
.thumb-list { flex: 1; overflow-y: auto; padding: 0 8px 8px; display: flex; flex-direction: column; gap: 6px; }
.thumb-card { display: flex; align-items: center; gap: 8px; padding: 8px; border-radius: 10px; border: 2px solid transparent; cursor: pointer; transition: all 0.15s; }
.thumb-card:hover { background: rgba(0,0,0,0.03); }
.thumb-card.active { border-color: #0071e3; background: rgba(0,113,227,0.05); }
.thumb-img-wrap { position: relative; width: 48px; height: 48px; flex-shrink: 0; border-radius: 6px; overflow: hidden; background: #e5e5ea; display: flex; align-items: center; justify-content: center; }
.thumb-img-wrap img { width: 100%; height: 100%; object-fit: cover; }
.thumb-status-icon { position: absolute; top: -4px; right: -4px; background: #fff; border-radius: 50%; padding: 1px; }
.thumb-name { font-size: 11px; color: #86868b; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; line-height: 1.3; }
.xray-main { flex: 1; overflow-y: auto; padding: 16px 20px; display: flex; flex-direction: column; gap: 12px; }
.result-card { display: flex; gap: 20px; background: #fff; border-radius: 16px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.04); flex-shrink: 0; }
.result-image { width: 220px; height: 220px; flex-shrink: 0; position: relative; cursor: pointer; border-radius: 10px; overflow: hidden; background: #e5e5ea; }
.result-image img { width: 100%; height: 100%; object-fit: contain; display: block; }
.image-overlay-hint { position: absolute; top: 8px; right: 8px; width: 28px; height: 28px; border-radius: 6px; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; color: #fff; opacity: 0; transition: opacity 0.2s; }
.result-image:hover .image-overlay-hint { opacity: 1; }
.result-info { display: flex; flex-direction: column; gap: 10px; flex: 1; min-width: 0; }
.file-name { display: flex; align-items: center; gap: 6px; font-size: 13px; color: #86868b; }
.file-name span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.verdict-badge { display: inline-flex; align-items: center; gap: 6px; padding: 10px 24px; border-radius: 20px; font-size: 18px; font-weight: 600; width: fit-content; }
.verdict-normal { background: #e8f5e9; color: #2e7d32; }
.verdict-warn { background: #fff3e0; color: #e65100; }
.verdict-danger { background: #ffebee; color: #c62828; }
.verdict-rejected { background: #fff8e1; color: #f59e0b; }
.verdict-reason { font-size: 14px; color: #666; line-height: 1.5; }
.result-columns { display: flex; gap: 12px; flex: 1; min-height: 0; }
.column { background: #fff; border-radius: 16px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.04); display: flex; flex-direction: column; overflow: hidden; }
.prob-column { flex: 1; min-width: 0; }
.report-column { flex: 1; min-width: 0; }
.column-title { font-size: 14px; font-weight: 600; color: #1d1d1f; margin-bottom: 12px; display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
.prob-list { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; padding-right: 4px; }
.prob-row { display: flex; flex-direction: column; gap: 4px; }
.prob-header { display: flex; justify-content: space-between; align-items: center; }
.prob-name { font-size: 13px; color: #1d1d1f; font-weight: 500; }
.prob-value { font-size: 13px; font-weight: 600; min-width: 38px; text-align: right; }
.prob-green { color: #34c759; }
.prob-orange { color: #f59e0b; }
.prob-red { color: #ff3b30; }
.prob-bar { height: 6px; background: #f0f0f3; border-radius: 3px; overflow: hidden; }
.prob-fill { height: 100%; border-radius: 3px; transition: width 0.5s ease; }
.bar-green { background: #34c759; }
.bar-orange { background: #f59e0b; }
.bar-red { background: #ff3b30; }
.report-text { flex: 1; overflow-y: auto; font-size: 14px; color: #1d1d1f; line-height: 1.8; white-space: pre-wrap; padding-right: 4px; }
.report-text :deep(strong) { color: #0071e3; font-weight: 600; }
.report-loading { display: flex; align-items: center; gap: 8px; color: #86868b; font-size: 13px; padding: 16px 0; }
.disclaimer { font-size: 12px; display: flex; align-items: center; gap: 6px; padding: 10px 14px; background: #fff8e1; border-radius: 10px; color: #856404; flex-shrink: 0; }
.full-image-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.85); z-index: 1000; display: flex; align-items: center; justify-content: center; }
.full-image-overlay img { max-width: 90vw; max-height: 90vh; border-radius: 8px; }
.close-btn { position: absolute; top: 20px; right: 20px; width: 40px; height: 40px; border: none; border-radius: 50%; background: rgba(255,255,255,0.2); color: #fff; cursor: pointer; display: flex; align-items: center; justify-content: center; }
</style>