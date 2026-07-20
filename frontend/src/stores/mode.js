/**
 * 文件名: src/stores/mode.js
 * 功能: 模式状态管理 - 刷新后恢复上次模式
 * 依赖: pinia
 */
import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export const useModeStore = defineStore('mode', () => {
  // 刷新后恢复上次使用的模式
  const saved = sessionStorage.getItem('localmind_active_mode')
  const activeMode = ref(saved || 'normal')
  const isTransitioning = ref(false)

  // 每次切换模式时持久化到 sessionStorage
  watch(activeMode, (val) => {
    sessionStorage.setItem('localmind_active_mode', val)
  })

  async function switchMode(mode) {
    if (isTransitioning.value || mode === activeMode.value) return
    isTransitioning.value = true
    activeMode.value = mode
    setTimeout(() => isTransitioning.value = false, 300)
  }

  return { activeMode, switchMode, isTransitioning }
})