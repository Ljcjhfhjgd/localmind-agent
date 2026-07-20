/**
 * 文件名: src/main.js
 * 功能: Vue入口
 */
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
createApp(App).use(createPinia()).mount('#app')