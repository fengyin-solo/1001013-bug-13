<template>
  <section class="page" data-module="greening-detail">
    <header class="page-head">
      <div>
        <h2>绿化管护详情</h2>
        <p class="page-desc">
          <button class="link" type="button" @click="goBack">← 返回列表</button>
        </p>
      </div>
    </header>

    <div v-if="entry" class="detail-card">
      <div class="detail-head">
        <h3>{{ entry['管护编号'] }} · {{ entry['管护区域'] }}</h3>
        <span class="status-badge" :class="{ closed: isClosed }">{{ entry['管护状态'] }}</span>
        <span v-if="isClosed" class="closed-tag">已结束 · 只读，不可改动</span>
      </div>

      <dl class="detail-grid">
        <div v-for="field in detailFields" :key="field" class="detail-item">
          <dt>{{ field }}</dt>
          <dd :class="{ note: field === '病虫害防治' }">
            {{ displayValue(field) }}
          </dd>
        </div>
      </dl>

      <div class="detail-actions">
        <template v-if="!isClosed">
          <button
            v-if="entry['管护状态'] === '待管护'"
            class="btn"
            type="button"
            :disabled="acting"
            @click="runSimpleAction('安排管护')"
          >
            安排管护
          </button>
          <template v-if="entry['管护状态'] === '管护中'">
            <button class="btn primary" type="button" :disabled="acting" @click="openPrevention">
              病虫害防治
            </button>
            <button class="btn" type="button" :disabled="acting" @click="runSimpleAction('登记补植')">
              登记补植
            </button>
          </template>
        </template>
        <p v-else class="readonly-hint">该管护记录已结束，仅支持查询，防治说明等历史信息完整保留。</p>
      </div>
      <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>
      <p v-if="infoMessage" class="info-text">{{ infoMessage }}</p>
    </div>

    <div v-else-if="loaded" class="detail-card empty-state">记录不存在或已归档。</div>
    <div v-else class="detail-card empty-state">明细加载中…</div>

    <PreventionDialog
      v-if="preventionVisible && entry"
      :entry="entry"
      :submitting="preventionSubmitting"
      @cancel="preventionVisible = false"
      @submit="submitPrevention"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'
import PreventionDialog from './PreventionDialog.vue'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/greening'
const detailFields = [
  '管护编号',
  '管护区域',
  '管护周期',
  '植被类型',
  '修剪频次',
  '浇水周期',
  '管护人员',
  '管护状态',
  '病虫害防治',
]
const closedStatuses = ['已管护', '待补植']

const route = useRoute()
const router = useRouter()

const entry = ref<Row | null>(null)
const loaded = ref(false)
const acting = ref(false)
const errorMessage = ref('')
const infoMessage = ref('')
const preventionVisible = ref(false)
const preventionSubmitting = ref(false)

const isClosed = computed(() =>
  entry.value ? closedStatuses.includes(String(entry.value['管护状态'] ?? '')) : false,
)

function displayValue(field: string) {
  if (!entry.value) return ''
  if (field === '病虫害防治') return String(entry.value[field] ?? '') || '暂无防治记录'
  return String(entry.value[field] ?? '') || '—'
}

function goBack() {
  void router.push({ name: 'greening' })
}

async function loadEntry() {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${route.params.id}`)
    if (!response.ok) {
      const payload = await response.json().catch(() => null)
      throw new Error(payload?.detail ?? '管护明细读取失败')
    }
    entry.value = await response.json()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '管护明细读取失败'
  } finally {
    loaded.value = true
  }
}

async function runSimpleAction(action: string) {
  if (acting.value) return
  acting.value = true
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${route.params.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok || !payload?.ok) {
      throw new Error(payload?.message ?? '操作未生效，请稍后重试')
    }
    infoMessage.value = payload.message
    await loadEntry()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '操作失败'
  } finally {
    acting.value = false
  }
}

function openPrevention() {
  // 进入弹窗前重新拉取服务端结论，确保与列表页、详情页看到的防治说明一致
  void loadEntry().then(() => {
    if (!entry.value) return
    if (closedStatuses.includes(String(entry.value['管护状态'] ?? ''))) {
      infoMessage.value = '该记录已结束，不可再登记防治'
      return
    }
    preventionVisible.value = true
  })
}

async function submitPrevention(note: string) {
  if (preventionSubmitting.value) return
  preventionSubmitting.value = true
  try {
    const response = await request(`${ENDPOINT}/${route.params.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action: '病虫害防治', 病虫害防治: note } }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok || !payload?.ok) {
      throw new Error(payload?.message ?? '防治登记未生效，请稍后重试')
    }
    preventionVisible.value = false
    infoMessage.value = payload.message
    await loadEntry()
  } catch (error) {
    // 交回弹窗内联展示，保留用户已填写的防治说明
    throw error instanceof Error ? error : new Error('防治登记失败')
  } finally {
    preventionSubmitting.value = false
  }
}

onMounted(loadEntry)
</script>

<style scoped>
.detail-card {
  background: #fff;
  border: 1px solid #d8dee6;
  border-radius: 10px;
  padding: 18px 20px;
}
.detail-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}
.detail-head h3 { margin: 0; font-size: 16px; }
.status-badge {
  background: #e8f1fe;
  color: #1f6feb;
  border-radius: 999px;
  padding: 2px 10px;
  font-size: 12px;
}
.status-badge.closed { background: #ecfdf3; color: #027a48; }
.closed-tag { color: #64748b; font-size: 12px; }
.detail-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px 20px;
  margin: 0;
}
.detail-item dt { font-size: 12px; color: #64748b; margin-bottom: 2px; }
.detail-item dd { margin: 0; font-size: 13px; word-break: break-all; }
.detail-item dd.note {
  grid-column: 1 / -1;
  background: #f8fafc;
  border-radius: 6px;
  padding: 8px 10px;
  min-height: 38px;
}
.detail-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 18px;
  border-top: 1px solid #eef2f6;
  padding-top: 14px;
}
.readonly-hint, .info-text { color: #1f6feb; font-size: 13px; margin: 0; }
</style>
