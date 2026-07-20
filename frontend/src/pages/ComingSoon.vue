<!--
文件名: src/pages/ComingSoon.vue
功能: 未开放模式的占位页
-->
<template>
  <div class="coming-soon">
    <div class="cs-icon">
      <Sparkles :size="48" color="#86868b" />
    </div>
    <h2>{{ title }}</h2>
    <p>新模式正在开发中，敬请期待</p>
    <div class="cs-features" v-if="features.length">
      <span v-for="f in features" :key="f" class="cs-feature">{{ f }}</span>
    </div>
  </div>
</template>

<script setup>
import { Sparkles } from 'lucide-vue-next'

defineProps({
  title: { type: String, default: '即将上线' },
  features: { type: Array, default: () => [] }
})
</script>

<style scoped>
.coming-soon {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: #86868b;
}

.cs-icon { margin-bottom: 8px; }
.coming-soon h2 { font-size: 20px; font-weight: 600; color: #1d1d1f; }
.coming-soon p { font-size: 14px; }

.cs-features {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.cs-feature {
  padding: 4px 14px;
  border-radius: 14px;
  font-size: 12px;
  color: #0071e3;
  background: rgba(0, 113, 227, 0.06);
}
</style>