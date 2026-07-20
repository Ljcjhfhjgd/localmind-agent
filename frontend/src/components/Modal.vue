<!--
文件名: src/components/Modal.vue
功能: 通用弹窗
-->
<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="open" class="modal-overlay" @click.self="$emit('close')">
        <div class="modal-box" :style="{ maxWidth: width }">
          <div v-if="title" class="modal-header">
            <h3>{{ title }}</h3>
            <button @click="$emit('close')">
              <X :size="16" />
            </button>
          </div>
          <div class="modal-body">
            <slot />
          </div>
          <div v-if="$slots.footer" class="modal-footer">
            <slot name="footer" />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { X } from 'lucide-vue-next'

defineProps({
  open: Boolean,
  title: String,
  width: { type: String, default: '400px' }
})

defineEmits(['close'])
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.2);
  backdrop-filter: blur(4px);
  z-index: 500;
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-box {
  width: 90%;
  background: #ffffff;
  border-radius: 16px;
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}

.modal-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: #1d1d1f;
  margin: 0;
}

.modal-header button {
  width: 28px; height: 28px;
  border: none; border-radius: 50%;
  background: rgba(0, 0, 0, 0.04);
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  color: #86868b;
}
.modal-header button:hover { background: rgba(0,0,0,0.08); }

.modal-body {
  padding: 16px 20px;
  font-size: 14px;
  color: #1d1d1f;
  line-height: 1.6;
}

.modal-footer {
  padding: 12px 20px;
  border-top: 1px solid rgba(0,0,0,0.06);
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.modal-enter-active { transition: all 0.25s ease; }
.modal-leave-active { transition: all 0.2s ease; }
.modal-enter-from { opacity: 0; }
.modal-enter-from .modal-box { transform: scale(0.95); opacity: 0; }
.modal-leave-to { opacity: 0; }
.modal-leave-to .modal-box { transform: scale(0.95); opacity: 0; }
</style>