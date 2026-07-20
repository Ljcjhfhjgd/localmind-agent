<!--
文件名: src/components/Toast.vue
功能: 全局消息提示 - success/error/warning/info + action按钮 + 监听toast事件
-->
<template>
  <Teleport to="body">
    <div class="toast-container">
      <TransitionGroup name="toast">
        <div v-for="t in toasts" :key="t.id" :class="['toast', t.type]">
          <component :is="iconMap[t.type]" :size="16" />
          <span class="toast-msg">{{ t.message }}</span>
          <button v-if="t.action" class="toast-action" @click="handleAction(t)">{{ t.action.label }}</button>
          <button class="toast-close" @click="remove(t.id)"><X :size="14" /></button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { CheckCircle, AlertCircle, AlertTriangle, Info, X } from 'lucide-vue-next'

const toasts = ref([])
let idCounter = 0
const MAX_TOASTS = 3

const iconMap = {
  success: CheckCircle,
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
}

function addToast(type, message, action, maxCount = MAX_TOASTS) {
  while (toasts.value.length >= maxCount) {
    toasts.value.shift()
  }
  const id = ++idCounter
  toasts.value.push({ id, type, message, action })
  setTimeout(() => remove(id), 4000)
}

function remove(id) {
  toasts.value = toasts.value.filter(t => t.id !== id)
}

function handleAction(t) {
  t.action?.onClick?.()
  remove(t.id)
}

function handleToastEvent(e) {
  const { type, message, action } = e.detail || {}
  if (type && message) {
    addToast(type, message, action)
  }
}

onMounted(() => { window.addEventListener('toast', handleToastEvent) })
onUnmounted(() => { window.removeEventListener('toast', handleToastEvent) })

defineExpose({ addToast, remove })
</script>

<style scoped>
.toast-container {
  position: fixed;
  top: 52px;
  right: 16px;
  z-index: 2000;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 380px;
}

.toast {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.1), 0 0 0 1px rgba(0,0,0,0.04);
  font-size: 13px;
  color: #1d1d1f;
  backdrop-filter: blur(12px);
  transition: all 0.25s ease;
}

.toast.success { border-left: 3px solid #34c759; }
.toast.success svg { color: #34c759; flex-shrink: 0; }

.toast.error { border-left: 3px solid #ff3b30; }
.toast.error svg { color: #ff3b30; flex-shrink: 0; }

.toast.warning { border-left: 3px solid #ff9500; }
.toast.warning svg { color: #ff9500; flex-shrink: 0; }

.toast.info { border-left: 3px solid #0071e3; }
.toast.info svg { color: #0071e3; flex-shrink: 0; }

.toast-msg { flex: 1; line-height: 1.4; }

.toast-action {
  padding: 4px 10px;
  border: 1px solid #0071e3;
  border-radius: 6px;
  background: transparent;
  color: #0071e3;
  font-size: 12px;
  cursor: pointer;
  font-family: inherit;
  white-space: nowrap;
}

.toast-action:hover {
  background: rgba(0,113,227,0.08);
}

.toast-close {
  width: 24px;
  height: 24px;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: #b0b0b5;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.toast-close:hover {
  background: rgba(0,0,0,0.05);
  color: #1d1d1f;
}

/* 过渡动画 */
.toast-enter-active { transition: all 0.3s ease; }
.toast-leave-active { transition: all 0.2s ease; }
.toast-enter-from { opacity: 0; transform: translateX(40px); }
.toast-leave-to { opacity: 0; transform: translateX(40px); }
</style>