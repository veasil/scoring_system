<template>
  <div>
    <h1 class="page-title">复盘测试</h1>
    <el-alert type="info" :closable="false" show-icon style="margin-bottom:12px"
      title="LLM 复盘报告生成测试" description="调用 /api/llm/story（默认 provider/model 取自系统设置）。可用「示例模板」快速填充一段对局数据。" />

    <el-row :gutter="16">
      <el-col :span="12">
        <el-card header="输入 Prompt">
          <div class="toolbar">
            <el-button size="small" @click="fillSample">填充示例对局</el-button>
            <span style="color:#909399">温度</span>
            <el-input-number v-model="temperature" :min="0" :max="1.2" :step="0.1" size="small" />
            <span style="color:#909399">最大tokens</span>
            <el-input-number v-model="maxTokens" :min="200" :max="4000" :step="200" size="small" />
          </div>
          <el-input v-model="prompt" type="textarea" :rows="16" placeholder="在此输入复盘 prompt…" />
          <el-button type="primary" :loading="loading" style="margin-top:10px" @click="run">生成复盘报告</el-button>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>
            <div style="display:flex; justify-content:space-between; align-items:center">
              <span>生成结果</span>
              <el-tag v-if="perf" size="small" type="success">{{ perf.provider }}/{{ perf.model }} · {{ perf.elapsed_ms }}ms</el-tag>
            </div>
          </template>
          <div v-loading="loading" style="min-height:360px; white-space:pre-wrap; line-height:1.7">{{ story || '（结果将显示在这里）' }}</div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { generateStory } from '../api/admin'

const prompt = ref('')
const temperature = ref(0.7)
const maxTokens = ref(1200)
const story = ref('')
const perf = ref(null)
const loading = ref(false)

function fillSample() {
  prompt.value = `你是「五力守望者」复盘导师。请根据下面一局桌游数据，为孩子家长生成一段温暖、具体、可执行的复盘报告（300字以内）。

【五力初始】安全力3 脑波力3 实感力3 创心力3 沟通力3
【关键选择】
1. 阶段:启蒙期 事件:吃饭时盯着动画看 → 选B(边吃边看) 安全力-1
2. 阶段:成长期 事件:同伴起冲突 → 选A(主动沟通) 沟通力+1
【五力结算】安全力2 脑波力3 实感力3 创心力3 沟通力4

请输出：1)整体表现概述 2)亮点 3)一个可在家练习的小建议。`
}

async function run() {
  if (!prompt.value.trim()) return ElMessage.warning('请输入 prompt')
  loading.value = true; story.value = ''; perf.value = null
  try {
    const { data } = await generateStory({ prompt: prompt.value, temperature: temperature.value, max_tokens: maxTokens.value })
    story.value = data.story
    perf.value = data.performance
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '生成失败（检查系统设置里的 LLM provider/key）')
  } finally { loading.value = false }
}
</script>
