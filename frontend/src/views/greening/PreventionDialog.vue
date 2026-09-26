<template>
  <div class="modal-mask" @click.self="cancel">
    <div class="modal">
      <h3 class="modal-title">病虫害防治登记</h3>
      <dl class="summary">
        <div><dt>管护编号</dt><dd>{{ entry['管护编号'] }}</dd></div>
        <div><dt>管护区域</dt><dd>{{ entry['管护区域'] }}</dd></div>
        <div><dt>管护人员</dt><dd>{{ entry['管护人员'] || '—' }}</dd></div>
        <div><dt>当前状态</dt><dd>{{ entry['管护状态'] }}</dd></div>
      </dl>

      <form @submit.prevent="onSubmit">
        <label class="form-item">
          <span>防治说明<em>*</em></span>
          <textarea
            v-model="note"
            rows="5"
            placeholder="请填写病虫害名称、用药与处置情况；提交后管护状态将变为「已管护」"
            :disabled="submitting"
          ></textarea>
        </label>
        <!-- 已有的防治结论原样回显，避免「填完丢失」 -->
        <div v-if="String(entry['病虫害防治'] ?? '')" class="prev-note">
          <span>已有防治记录：</span>{{ entry['病虫害防治'] }}
        </div>
        <p v-if="errorText" class="error-text">{{ errorText }}</p>
        <div class="modal-actions">
          <button class="btn ghost" type="button" :disabled="submitting" @click="cancel">取消</button>
          <button class="btn primary" type="submit" :disabled="submitting">
            {{ submitting ? '提交中…' : '提交防治登记' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

type Row = Record<string, string | number | null>

const props = defineProps<{
  entry: Row
  submitting?: boolean
}>()

const emit = defineEmits<{
  (e: 'cancel'): void
  (e: 'submit', note: string): Promise<void> | void
}>()

const note = ref(String(props.entry['病虫害防治'] ?? ''))
const errorText = ref('')

watch(
  () => props.entry.id,
  () => {
    note.value = String(props.entry['病虫害防治'] ?? '')
    errorText.value = ''
  },
)

async function onSubmit() {
  errorText.value = ''
  if (!note.value.trim()) {
    errorText.value = '请先填写病虫害防治说明再提交'
    return
  }
  try {
    await emit('submit', note.value.trim())
  } catch (error) {
    errorText.value = error instanceof Error ? error.message : '防治登记失败'
  }
}

function cancel() {
  if (!props.submitting) emit('cancel')
}
</script>

<style scoped>
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 30;
}
.modal {
  width: 560px;
  max-width: calc(100vw - 32px);
  background: #fff;
  border-radius: 10px;
  padding: 20px 22px;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.2);
}
.modal-title { margin: 0 0 12px; font-size: 16px; }
.summary {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px 16px;
  margin: 0 0 14px;
  font-size: 13px;
}
.summary div { display: flex; gap: 8px; }
.summary dt { color: #64748b; margin: 0; min-width: 56px; }
.summary dd { margin: 0; }
.form-item { display: block; }
.form-item span { display: block; font-size: 12px; color: #475569; margin-bottom: 4px; }
.form-item em { color: #b42318; font-style: normal; margin-left: 2px; }
.form-item textarea {
  width: 100%;
  border: 1px solid #d8dee6;
  border-radius: 6px;
  padding: 8px 10px;
  font-size: 13px;
  resize: vertical;
}
.prev-note {
  margin-top: 8px;
  padding: 8px 10px;
  background: #f1f5f9;
  border-radius: 6px;
  font-size: 12px;
  color: #334155;
}
.prev-note span { color: #64748b; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
</style>
