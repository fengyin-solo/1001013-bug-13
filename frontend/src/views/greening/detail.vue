<template>
  <section class="page" data-module="greening-detail">
    <header class="page-head">
      <div>
        <h2>绿化管护详情</h2>
        <p class="page-desc">详情、列表与防治弹窗读取同一条台账记录，状态结论保持一致。</p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="goBack">返回列表</button>
      </div>
    </header>

    <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>

    <template v-if="entry">
      <table class="data-table detail-table">
        <tbody>
          <tr v-for="field in detailFields" :key="field">
            <th>{{ field }}</th>
            <td>{{ entry[field] || '—' }}</td>
          </tr>
        </tbody>
      </table>

      <div class="detail-actions">
        <template v-if="!isEnded">
          <button
            v-for="action in availableActions"
            :key="action"
            class="btn"
            :class="{ primary: action === '防治登记' }"
            type="button"
            @click="onAction(action)"
          >
            {{ action }}
          </button>
        </template>
        <p v-else class="muted-text">该记录已结束（{{ entry['管护状态'] }}），仅供查询，不能再改动。</p>
      </div>

      <p v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</p>
    </template>

    <div v-if="pestVisible" class="dialog-mask" @click.self="pestVisible = false">
      <div class="dialog">
        <header class="dialog-head">
          <h3>防治登记 · {{ entry?.['管护编号'] }}</h3>
          <button class="link" type="button" @click="pestVisible = false">关闭</button>
        </header>
        <form class="dialog-body" @submit.prevent="submitPest">
          <p v-if="entry?.['病虫害防治']" class="dialog-tip">
            已有防治说明：{{ entry['病虫害防治'] }}
          </p>
          <label class="form-item">
            <span>防治说明<em class="required-mark">*</em></span>
            <textarea
              v-model="pestNote"
              rows="4"
              placeholder="记录病虫害情况与防治措施，提交后状态流转为已管护"
            ></textarea>
          </label>
          <footer class="dialog-foot">
            <button class="btn ghost" type="button" @click="pestVisible = false">取消</button>
            <button class="btn primary" type="submit" :disabled="submitting">
              {{ submitting ? '提交中…' : '确认防治登记' }}
            </button>
          </footer>
        </form>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/greening'
const detailFields = ["管护编号", "管护区域", "管护周期", "植被类型", "修剪频次", "浇水周期", "病虫害防治", "管护人员", "管护状态"]
const endedStatuses = ["已管护"]
// 各状态在详情页可执行的动作；防治登记会打开弹窗填写防治说明
const statusActions: Record<string, string[]> = {
  "待管护": ["安排管护", "登记补植"],
  "管护中": ["防治登记", "登记补植"],
  "待补植": ["补植完成"],
}

const route = useRoute()
const router = useRouter()
const entry = ref<Row | null>(null)
const errorMessage = ref('')
const noticeMessage = ref('')
const pestVisible = ref(false)
const pestNote = ref('')
const submitting = ref(false)

const isEnded = computed(() => endedStatuses.includes(String(entry.value?.['管护状态'] ?? '')))
const availableActions = computed(() => statusActions[String(entry.value?.['管护状态'] ?? '')] ?? [])

function goBack() {
  void router.push('/greening')
}

function onAction(action: string) {
  if (action === '防治登记') {
    pestNote.value = ''
    pestVisible.value = true
    return
  }
  void runAction(action)
}

async function runAction(action: string, note = '') {
  if (!entry.value || submitting.value) return
  errorMessage.value = ''
  noticeMessage.value = ''
  submitting.value = true
  try {
    const response = await request(`${ENDPOINT}/${entry.value.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action, 防治说明: note } }),
    })
    const payload = await response.json()
    if (!payload.ok) {
      throw new Error(payload.message || '绿化管护动作未生效')
    }
    noticeMessage.value = payload.message
    pestVisible.value = false
    await loadEntry()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '绿化管护操作失败'
  } finally {
    submitting.value = false
  }
}

async function submitPest() {
  const note = pestNote.value.trim()
  if (!note) {
    errorMessage.value = '防治说明不能为空'
    return
  }
  await runAction('防治登记', note)
}

async function loadEntry() {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${route.params.id}`)
    if (!response.ok) {
      throw new Error('绿化管护详情读取失败')
    }
    entry.value = await response.json()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '绿化管护详情读取失败'
  }
}

onMounted(loadEntry)
</script>
