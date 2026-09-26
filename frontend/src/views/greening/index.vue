<template>
  <section class="page" data-module="greening">
    <header class="page-head">
      <div>
        <h2>绿化管护管理</h2>
        <p class="page-desc">维护绿化管护，围绕管护区域、修剪频次、浇水周期与病虫害防治做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记绿化管护</button>
        <button class="btn" type="button" @click="exportRows">导出绿化管护清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in statsCards" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>管护编号 / 区域</span>
        <input v-model="keyword" placeholder="按管护编号或区域检索" />
      </label>
      <label class="filter-item">
        <span>管护状态</span>
        <select v-model="statusFilter">
          <option value="">全部状态</option>
          <option v-for="s in statuses" :key="s" :value="s">{{ s }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column" :title="column === '病虫害防治' ? String(row[column] ?? '') : ''">
            <span v-if="column === '管护编号'" class="link" @click="openDetail(row)">{{ row[column] }}</span>
            <span v-else class="cell-clamp">{{ row[column] || '—' }}</span>
          </td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(row)">查看详情</button>
            <template v-if="!isClosed(row)">
              <template v-if="row['管护状态'] === '待管护'">
                <button class="link" type="button" @click="runSimpleAction('安排管护', row)">安排管护</button>
              </template>
              <template v-else-if="row['管护状态'] === '管护中'">
                <button class="link" type="button" @click="openPrevention(row)">病虫害防治</button>
                <button class="link" type="button" @click="runSimpleAction('登记补植', row)">登记补植</button>
              </template>
            </template>
            <span v-else class="closed-tag">已结束·只读</span>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无绿化管护数据，可先登记绿化管护</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条绿化管护记录（含历史已结束记录）</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      <span v-else-if="infoMessage" class="info-text">{{ infoMessage }}</span>
    </footer>

    <!-- 登记弹窗 -->
    <div v-if="createVisible" class="modal-mask" @click.self="closeCreate">
      <div class="modal">
        <h3 class="modal-title">登记绿化管护</h3>
        <p class="modal-hint">管护编号由系统自动生成；同一管护区域同一管护周期只能有一条在办记录。</p>
        <form @submit.prevent="submitCreate">
          <label v-for="field in createFields" :key="field.key" class="form-item">
            <span>{{ field.label }}<em v-if="field.required">*</em></span>
            <input
              v-model="createForm[field.key]"
              :placeholder="`请输入${field.label}`"
              :disabled="submitting"
            />
          </label>
          <p v-if="formError" class="error-text">{{ formError }}</p>
          <div class="modal-actions">
            <button class="btn ghost" type="button" :disabled="submitting" @click="closeCreate">取消</button>
            <button class="btn primary" type="submit" :disabled="submitting">
              {{ submitting ? '提交中…' : '提交登记' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- 病虫害防治弹窗（列表入口） -->
    <PreventionDialog
      v-if="preventionTarget"
      :entry="preventionTarget"
      :submitting="preventionSubmitting"
      @cancel="preventionTarget = null"
      @submit="submitPrevention"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { request } from '@/api/client'
import PreventionDialog from './PreventionDialog.vue'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/greening'
const columns = ['管护编号', '管护区域', '植被类型', '修剪频次', '浇水周期', '病虫害防治', '管护人员', '管护状态']
const statuses = ['待管护', '管护中', '已管护', '待补植']
const closedStatuses = ['已管护', '待补植']

const router = useRouter()

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const infoMessage = ref('')
const keyword = ref('')
const statusFilter = ref('')

const statsCards = computed(() => [
  { label: '待管护区域', value: rows.value.filter((r) => r['管护状态'] === '待管护').length },
  { label: '管护中区域', value: rows.value.filter((r) => r['管护状态'] === '管护中').length },
  { label: '待补植区域', value: rows.value.filter((r) => r['管护状态'] === '待补植').length },
])

const createFields = [
  { key: '管护区域', label: '管护区域', required: true },
  { key: '植被类型', label: '植被类型', required: true },
  { key: '管护周期', label: '管护周期（如 2026-09）', required: true },
  { key: '修剪频次', label: '修剪频次', required: false },
  { key: '浇水周期', label: '浇水周期', required: false },
  { key: '管护人员', label: '管护人员', required: false },
] as const

const createVisible = ref(false)
const submitting = ref(false)
const formError = ref('')
const emptyForm = () => ({
  管护区域: '',
  植被类型: '',
  管护周期: defaultPeriod(),
  修剪频次: '',
  浇水周期: '',
  管护人员: '',
})
const createForm = reactive(emptyForm())

function defaultPeriod() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

function isClosed(row: Row) {
  return closedStatuses.includes(String(row['管护状态'] ?? ''))
}

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  Object.assign(createForm, emptyForm())
  formError.value = ''
  createVisible.value = true
}

function closeCreate() {
  if (submitting.value) return
  createVisible.value = false
}

async function submitCreate() {
  if (submitting.value) return
  formError.value = ''
  submitting.value = true
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: { ...createForm } }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok || !payload?.ok) {
      throw new Error(payload?.message ?? '绿化管护登记未生效，请稍后重试')
    }
    createVisible.value = false
    infoMessage.value = payload.duplicated ? payload.message : '绿化管护已登记'
    await reload()
  } catch (error) {
    formError.value = error instanceof Error ? error.message : '绿化管护登记失败'
  } finally {
    submitting.value = false
  }
}

function openDetail(row: Row) {
  void router.push({ name: 'greening-detail', params: { id: row.id } })
}

// 列表内直接执行的无表单动作
async function runSimpleAction(action: string, row: Row) {
  errorMessage.value = ''
  infoMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok || !payload?.ok) {
      throw new Error(payload?.message ?? '操作未生效，请稍后重试')
    }
    infoMessage.value = payload.message
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '绿化管护操作失败'
  }
}

// 病虫害防治弹窗
const preventionTarget = ref<Row | null>(null)
const preventionSubmitting = ref(false)

function openPrevention(row: Row) {
  errorMessage.value = ''
  infoMessage.value = ''
  // 始终以服务端最新数据为准，保证列表、详情、弹窗三处结论一致
  void refreshRow(row).then((latest) => {
    if (!latest) return
    if (isClosed(latest)) {
      infoMessage.value = `${latest['管护编号']} 已结束（${latest['管护状态']}），不可再登记防治`
      void reload()
      return
    }
    preventionTarget.value = latest
  })
}

async function refreshRow(row: Row): Promise<Row | null> {
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) throw new Error()
    return (await response.json()) as Row
  } catch {
    errorMessage.value = '管护明细读取失败，请稍后重试'
    return null
  }
}

async function submitPrevention(note: string) {
  if (!preventionTarget.value || preventionSubmitting.value) return
  preventionSubmitting.value = true
  try {
    const response = await request(`${ENDPOINT}/${preventionTarget.value.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action: '病虫害防治', 病虫害防治: note } }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok || !payload?.ok) {
      throw new Error(payload?.message ?? '防治登记未生效，请稍后重试')
    }
    preventionTarget.value = null
    infoMessage.value = payload.message
    await reload()
  } catch (error) {
    // 错误透传给弹窗内联展示，避免填好的说明丢失
    throw error instanceof Error ? error : new Error('防治登记失败')
  } finally {
    preventionSubmitting.value = false
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (keyword.value.trim()) query.set('keyword', keyword.value.trim())
  if (statusFilter.value) query.set('status', statusFilter.value)
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error('绿化管护列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '绿化管护列表读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.info-text { color: #1f6feb; }
.closed-tag { color: #64748b; font-size: 12px; }
.cell-clamp {
  display: inline-block;
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: bottom;
}
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
}
.modal {
  width: 520px;
  max-width: calc(100vw - 32px);
  background: #fff;
  border-radius: 10px;
  padding: 20px 22px;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.2);
}
.modal-title { margin: 0; font-size: 16px; }
.modal-hint { margin: 6px 0 14px; font-size: 12px; color: #64748b; }
.form-item { display: block; margin-bottom: 12px; }
.form-item span { display: block; font-size: 12px; color: #475569; margin-bottom: 4px; }
.form-item em { color: #b42318; font-style: normal; margin-left: 2px; }
.form-item input {
  width: 100%;
  border: 1px solid #d8dee6;
  border-radius: 6px;
  padding: 7px 10px;
  font-size: 13px;
}
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
</style>
