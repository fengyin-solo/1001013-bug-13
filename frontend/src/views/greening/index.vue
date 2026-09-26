<template>
  <section class="page" data-module="greening">
    <header class="page-head">
      <div>
        <h2>绿化管护管理</h2>
        <p class="page-desc">维护绿化管护台账：同一管护区域同期只建一条记录，防治登记后状态流转为已管护。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="createVisible = true">登记绿化管护</button>
        <button class="btn" type="button" @click="exportRows">导出绿化管护清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>管护编号</span>
        <input v-model="keyword" placeholder="按管护编号检索" />
      </label>
      <label class="filter-item">
        <span>管护状态</span>
        <select v-model="statusFilter">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] || '—' }}</td>
          <td class="row-actions">
            <button class="link" type="button" @click="goDetail(row)">详情</button>
            <button
              v-for="action in rowActions(row)"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
            <span v-if="isEnded(row)" class="muted-text">已结束，只读</span>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无绿化管护数据，可先登记绿化管护</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条绿化管护记录</span>
      <span v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="createVisible" class="dialog-mask" @click.self="closeCreate">
      <div class="dialog">
        <header class="dialog-head">
          <h3>登记绿化管护</h3>
          <button class="link" type="button" @click="closeCreate">关闭</button>
        </header>
        <form class="dialog-body form-grid" @submit.prevent="submitCreate">
          <label v-for="field in createFields" :key="field.name" class="form-item">
            <span>{{ field.label }}<em v-if="field.required" class="required-mark">*</em></span>
            <input v-model="createForm[field.name]" :placeholder="field.placeholder" />
          </label>
          <p class="dialog-tip">同一管护区域在同一管护周期只保留一条记录，重复提交不会重复建档。</p>
          <footer class="dialog-foot">
            <button class="btn ghost" type="button" @click="closeCreate">取消</button>
            <button class="btn primary" type="submit" :disabled="submitting">
              {{ submitting ? '提交中…' : '提交登记' }}
            </button>
          </footer>
        </form>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/greening'
const columns = ["管护编号", "管护区域", "管护周期", "植被类型", "修剪频次", "浇水周期", "病虫害防治", "管护人员", "管护状态"]
const statuses = ["待管护", "管护中", "待补植", "已管护"]
const endedStatuses = ["已管护"]
// 各状态在列表页可执行的快捷动作；防治登记在详情页弹窗里完成
const statusActions: Record<string, string[]> = {
  "待管护": ["安排管护", "登记补植"],
  "管护中": ["登记补植"],
  "待补植": ["补植完成"],
}
const createFields = [
  { name: '管护区域', label: '管护区域', required: true, placeholder: '如：城东快速路中央绿化带' },
  { name: '管护周期', label: '管护周期', required: true, placeholder: '如：2026-09' },
  { name: '植被类型', label: '植被类型', required: true, placeholder: '如：常绿灌木' },
  { name: '修剪频次', label: '修剪频次', required: false, placeholder: '如：每月2次' },
  { name: '浇水周期', label: '浇水周期', required: false, placeholder: '如：每周3次' },
  { name: '管护人员', label: '管护人员', required: false, placeholder: '如：张伟' },
]

const router = useRouter()
const rows = ref<Row[]>([])
const total = ref(0)
const allRows = ref<Row[]>([])
const keyword = ref('')
const statusFilter = ref('')
const errorMessage = ref('')
const noticeMessage = ref('')
const createVisible = ref(false)
const submitting = ref(false)
const createForm = reactive<Record<string, string>>({})

const stats = computed(() => [
  { label: '待管护区域', value: countByStatus('待管护') },
  { label: '管护中区域', value: countByStatus('管护中') },
  { label: '待补植区域', value: countByStatus('待补植') },
  { label: '已管护区域', value: countByStatus('已管护') },
])

function countByStatus(status: string) {
  return allRows.value.filter((row) => row['管护状态'] === status).length
}

function isEnded(row: Row) {
  return endedStatuses.includes(String(row['管护状态'] ?? ''))
}

function rowActions(row: Row) {
  return statusActions[String(row['管护状态'] ?? '')] ?? []
}

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function goDetail(row: Row) {
  void router.push(`/greening/${row.id}`)
}

function closeCreate() {
  createVisible.value = false
  Object.keys(createForm).forEach((key) => { createForm[key] = '' })
}

async function submitCreate() {
  if (submitting.value) return
  errorMessage.value = ''
  noticeMessage.value = ''
  submitting.value = true
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: { ...createForm } }),
    })
    const payload = await response.json()
    if (!payload.ok) {
      throw new Error(payload.message || '绿化管护登记失败')
    }
    noticeMessage.value = payload.message
    closeCreate()
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '绿化管护登记失败'
  } finally {
    submitting.value = false
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json()
    if (!payload.ok) {
      throw new Error(payload.message || '绿化管护动作未生效')
    }
    noticeMessage.value = payload.message
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '绿化管护操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (keyword.value) query.set('keyword', keyword.value)
  if (statusFilter.value) query.set('status', statusFilter.value)
  try {
    const [listResponse, allResponse] = await Promise.all([
      request(`${ENDPOINT}?${query.toString()}`),
      request(`${ENDPOINT}?size=200`),
    ])
    if (!listResponse.ok || !allResponse.ok) {
      throw new Error('绿化管护列表读取失败')
    }
    const payload = await listResponse.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    const allPayload = await allResponse.json()
    allRows.value = allPayload.items ?? []
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '绿化管护列表读取失败'
  }
}

onMounted(reload)
</script>
