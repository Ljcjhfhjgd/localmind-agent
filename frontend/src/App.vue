<!--
文件名: src/App.vue
功能: 根组件 - Toast + 全局 fetch 拦截
-->
<template>
  <AppShell />
  <Toast ref="toastRef" />
</template>

<script setup>
import { ref, provide, onMounted } from 'vue'
import AppShell from '@/components/AppShell.vue'
import Toast from '@/components/Toast.vue'

const toastRef = ref(null)
provide('toast', toastRef)

function addToast(type, message, action) {
  toastRef.value?.addToast(type, message, action)
}

// 3 秒内同类型 Toast 不重复，最多同时显示 3 个
let lastToastTime = 0
let lastToastMsg = ''
function throttledToast(type, message, action) {
  const now = Date.now()
  if (now - lastToastTime < 3000 && message === lastToastMsg) return
  lastToastTime = now
  lastToastMsg = message
  toastRef.value?.addToast(type, message, action, 3)
}

onMounted(() => {
  const originalFetch = window.fetch

  window.fetch = async function(url, options = {}) {
    const urlStr = typeof url === 'string' ? url : url.url

    const apiKey = localStorage.getItem('api_key') || ''
    const headers = new Headers(options.headers || {})
    if (!headers.has('X-API-Key')) {
      headers.set('X-API-Key', apiKey)
    }

    const response = await originalFetch(url, { ...options, headers })

    if (response.status === 403) {
      const cloned = response.clone()
      try {
        const body = await cloned.json()
        const detail = body?.detail || ''
        if (detail === 'api_key_invalid') {
          throttledToast('error', 'API Key 无效，请在设置中配置正确的 Key', {
            label: '去设置',
            onClick: () => window.dispatchEvent(new CustomEvent('open-settings'))
          })
        } else if (detail === 'email_auth_failed') {
          throttledToast('error', '邮箱认证失败，请检查授权码是否正确')
        } else {
          throttledToast('error', '请求被拒绝，请检查 API Key 设置')
        }
      } catch {
        throttledToast('error', '请求被拒绝 (403)')
      }
    }

    return response
  }
})
</script>

<style>
*,
*::before,
*::after { box-sizing: border-box; }

html, body {
  margin: 0; padding: 0; height: 100%; overflow: hidden;
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', Roboto, sans-serif;
  -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale;
  background: #f5f5f7;
}

#app { height: 100%; }

::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.1); border-radius: 2px; }
::-webkit-scrollbar-thumb:hover { background: rgba(0,0,0,0.2); }

.code-block { background: #1e1e1e; border-radius: 10px; margin: 8px 0; overflow: hidden; }
.code-block-header { display: flex; justify-content: space-between; align-items: center; padding: 6px 12px; background: #2d2d2d; color: #999; font-size: 12px; }
.code-block-header span { font-size: 12px; color: #999; }
.copy-btn { padding: 4px 12px; border: 1px solid #555; border-radius: 4px; background: transparent; color: #ccc; cursor: pointer; font-size: 11px; font-family: inherit; transition: all 0.15s; }
.copy-btn:hover { background: #444; color: #fff; }
.code-block pre { margin: 0; padding: 12px; background: #1e1e1e; color: #d4d4d4; overflow-x: auto; font-size: 13px; line-height: 1.6; }
.code-block code { font-family: 'SF Mono', 'Consolas', 'Liberation Mono', monospace; font-size: 13px; }
</style>