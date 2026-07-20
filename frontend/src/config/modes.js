/**
 * 文件名: src/config/modes.js
 * 功能: 模式配置
 */
export const ALL_MODES = {
  normal: {
    id: 'normal',
    name: '日常',
    icon: 'MessageCircle',
    description: '随时提问，全能应答',
  },
  agent: {
    id: 'agent',
    name: 'Agent',
    icon: 'Bot',
    description: 'ReAct 推理 + 工具调用',
  },
  rag: {
    id: 'rag',
    name: '知识库',
    icon: 'Database',
    description: '文档上传，RAG 检索',
  },
  xray: {
    id: 'xray',
    name: '胸片',
    icon: 'Scan',
    description: 'AI 辅助胸片诊断',
  },
  email: {
    id: 'email',
    name: '邮件',
    icon: 'Mail',
    description: 'AI 生成邮件草案',
  },
  comingsoon: {
    id: 'comingsoon',
    name: '敬请期待',
    icon: 'Sparkles',
    description: '更多功能即将上线',
  },
}

export const MODE_ORDER = ['normal', 'agent', 'rag', 'xray', 'email', 'comingsoon']