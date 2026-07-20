<!--
文件名: src/components/CodeBlock.vue
功能: 代码块组件 - 折叠/复制/语言识别/Apple浅色
-->
<template>
  <div class="code-block">
    <div class="code-block-header">
      <div class="header-left">
        <button class="toggle-btn" @click="collapsed = !collapsed" title="折叠代码">
          <ChevronDown v-if="!collapsed" :size="14" />
          <ChevronRight v-else :size="14" />
        </button>
        <span>{{ displayLang }}</span>
      </div>
      <button class="copy-btn" @click="copy" title="复制代码">
        <Copy v-if="!copied" :size="20" />
        <CheckCircle v-else :size="20" color="#34c759" />
      </button>
    </div>
    <pre v-show="!collapsed"><code v-html="escapedCode"></code></pre>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Copy, CheckCircle, ChevronDown, ChevronRight } from 'lucide-vue-next'

const props = defineProps({
  lang: { type: String, default: '' },
  code: { type: String, default: '' },
})

const copied = ref(false)
const collapsed = ref(false)

const displayLang = computed(() => {
  let lang = (props.lang || '').toLowerCase()
  lang = lang.replace(/^(python|javascript|typescript|java|ruby|go|rust|cpp|csharp|c|bash|shell|sql|html|css|json|yaml|xml|markdown|text|sh|rb|rs|ts|js|py|md|yml).*$/i, '$1')
  if (!lang) return 'code'
  const map = {
    'py': 'python', 'js': 'javascript', 'ts': 'typescript', 'rb': 'ruby',
    'go': 'go', 'rs': 'rust', 'java': 'java', 'c': 'c', 'cpp': 'c++',
    'cs': 'c#', 'sh': 'shell', 'bash': 'bash', 'sql': 'sql',
    'html': 'html', 'css': 'css', 'json': 'json', 'yaml': 'yaml', 'md': 'markdown',
  }
  return map[lang] || lang
})

const escapedCode = computed(() => {
  return props.code.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
})

function copy() {
  navigator.clipboard.writeText(props.code).then(() => {
    copied.value = true
    setTimeout(() => (copied.value = false), 2000)
  })
}
</script>

<style scoped>
.code-block {
  background: #f5f5f7;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 10px;
  margin: 10px 0;
  overflow: hidden;
}
.code-block-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 10px;
  background: rgba(0, 0, 0, 0.03);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}
.header-left {
  display: flex;
  align-items: center;
  gap: 4px;
}
.toggle-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: #86868b;
  cursor: pointer;
  transition: all 0.15s;
}
.toggle-btn:hover {
  background: rgba(0, 0, 0, 0.05);
  color: #1d1d1f;
}
.code-block-header span {
  font-size: 12px;
  font-weight: 500;
  color: #86868b;
  text-transform: lowercase;
}
.copy-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #86868b;
  cursor: pointer;
  transition: all 0.15s;
}
.copy-btn:hover {
  background: rgba(0, 0, 0, 0.05);
  color: #0071e3;
}
.code-block pre {
  margin: 0;
  padding: 14px 16px;
  background: #ffffff;
  color: #1d1d1f;
  overflow-x: auto;
  font-size: 13px;
  line-height: 1.7;
}
.code-block code {
  font-family: 'SF Mono', 'Consolas', 'Liberation Mono', monospace;
  font-size: 13px;
}
</style>