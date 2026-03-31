<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import {
  fetchUsageRecords,
  fetchUsageSummary,
  type EndpointBucket,
  type UsageRecordRow,
  type UsageSummary,
} from "@/api/usage";

const rangeDays = ref(30);
const summary = ref<UsageSummary | null>(null);
const records = ref<UsageRecordRow[]>([]);
const recordsTotal = ref(0);
const page = ref(1);
const pageSize = ref(15);
const loadingSummary = ref(false);
const loadingTable = ref(false);

const emptyBucket = (): EndpointBucket => ({
  turns: 0,
  embed_prompt_tokens: 0,
  embed_total_tokens: 0,
  chat_prompt_tokens: 0,
  chat_completion_tokens: 0,
  chat_total_tokens: 0,
});

const localBucket = computed(() =>
  summary.value?.by_endpoint["local"] ?? emptyBucket()
);
const remoteBucket = computed(() =>
  summary.value?.by_endpoint["remote"] ?? emptyBucket()
);

function fmt(n: number | null | undefined): string {
  if (n == null) return "—";
  return n.toLocaleString();
}

function fmtTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

async function loadSummary() {
  loadingSummary.value = true;
  try {
    const { data } = await fetchUsageSummary(rangeDays.value);
    summary.value = data;
  } catch {
    ElMessage.error("加载汇总失败");
  } finally {
    loadingSummary.value = false;
  }
}

async function loadRecords() {
  loadingTable.value = true;
  try {
    const { data } = await fetchUsageRecords({
      skip: (page.value - 1) * pageSize.value,
      limit: pageSize.value,
      days: rangeDays.value,
    });
    records.value = data.items;
    recordsTotal.value = data.total;
  } catch {
    ElMessage.error("加载明细失败");
  } finally {
    loadingTable.value = false;
  }
}

async function refresh() {
  await loadSummary();
  await loadRecords();
}

onMounted(refresh);

watch(rangeDays, () => {
  page.value = 1;
});

watch([rangeDays, page], () => {
  loadSummary();
  loadRecords();
});

const presetDays = [
  { label: "近 7 天", value: 7 },
  { label: "近 30 天", value: 30 },
  { label: "近 90 天", value: 90 },
];
</script>

<template>
  <div class="usage-page">
    <header class="page-head">
      <h1 class="title">用量统计</h1>
      <p class="hint">
        统计每次问答中的<strong>检索向量（embedding）</strong>与<strong>对话生成（chat）</strong>的
        token；数值优先来自上游 API，缺失时为<strong>估算</strong>。本地/在线按对话模型 Base
        URL 是否本机地址划分（与 Ollama 一致）。
      </p>
      <div class="toolbar">
        <el-radio-group v-model="rangeDays" size="default">
          <el-radio-button
            v-for="p in presetDays"
            :key="p.value"
            :label="p.value"
          >
            {{ p.label }}
          </el-radio-button>
        </el-radio-group>
        <el-button :loading="loadingSummary || loadingTable" @click="refresh">
          刷新
        </el-button>
      </div>
    </header>

    <el-skeleton v-if="loadingSummary && !summary" :rows="4" animated />

    <template v-else-if="summary">
      <section class="cards">
        <el-card shadow="hover" class="card">
          <template #header>总问答轮次</template>
          <el-statistic :value="summary.totals.turns" />
        </el-card>
        <el-card shadow="hover" class="card card-local">
          <template #header>本地模型（对话）</template>
          <el-statistic
            title="轮次"
            :value="localBucket.turns"
            class="stat-line"
          />
          <div class="sub-stats">
            <span>Chat 输入 token</span>
            <strong>{{ fmt(localBucket.chat_prompt_tokens) }}</strong>
          </div>
          <div class="sub-stats">
            <span>Chat 输出 token</span>
            <strong>{{ fmt(localBucket.chat_completion_tokens) }}</strong>
          </div>
          <div class="sub-stats">
            <span>检索 embedding</span>
            <strong>{{ fmt(localBucket.embed_prompt_tokens) }}</strong>
          </div>
        </el-card>
        <el-card shadow="hover" class="card card-remote">
          <template #header>在线模型（对话）</template>
          <el-statistic
            title="轮次"
            :value="remoteBucket.turns"
            class="stat-line"
          />
          <div class="sub-stats">
            <span>Chat 输入 token</span>
            <strong>{{ fmt(remoteBucket.chat_prompt_tokens) }}</strong>
          </div>
          <div class="sub-stats">
            <span>Chat 输出 token</span>
            <strong>{{ fmt(remoteBucket.chat_completion_tokens) }}</strong>
          </div>
          <div class="sub-stats">
            <span>检索 embedding</span>
            <strong>{{ fmt(remoteBucket.embed_prompt_tokens) }}</strong>
          </div>
        </el-card>
        <el-card shadow="hover" class="card card-total">
          <template #header>全量合计（当前时间范围）</template>
          <div class="sub-stats">
            <span>Chat 总 token（约）</span>
            <strong>{{ fmt(summary.totals.chat_total_tokens) }}</strong>
          </div>
          <div class="sub-stats">
            <span>Embedding 侧（prompt 计）</span>
            <strong>{{ fmt(summary.totals.embed_prompt_tokens) }}</strong>
          </div>
        </el-card>
      </section>

      <el-card v-if="summary.by_model.length" class="model-card" shadow="never">
        <template #header>按对话模型</template>
        <el-table :data="summary.by_model" size="small" stripe>
          <el-table-column prop="display_name" label="模型" min-width="140">
            <template #default="{ row }">
              {{ row.display_name || `ID ${row.chat_model_id}` }}
            </template>
          </el-table-column>
          <el-table-column prop="turns" label="轮次" width="88" />
          <el-table-column label="Chat 入" width="100">
            <template #default="{ row }">{{ fmt(row.chat_prompt_tokens) }}</template>
          </el-table-column>
          <el-table-column label="Chat 出" width="100">
            <template #default="{ row }">{{ fmt(row.chat_completion_tokens) }}</template>
          </el-table-column>
          <el-table-column label="检索 embedding" width="120">
            <template #default="{ row }">{{ fmt(row.embed_prompt_tokens) }}</template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>

    <el-card class="table-card" shadow="never">
      <template #header>明细</template>
      <el-table
        v-loading="loadingTable"
        :data="records"
        stripe
        style="width: 100%"
        empty-text="暂无记录，先去对话页提问吧"
      >
        <el-table-column label="时间" min-width="160">
          <template #default="{ row }: { row: UsageRecordRow }">
            {{ fmtTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="会话" min-width="120" show-overflow-tooltip>
          <template #default="{ row }: { row: UsageRecordRow }">
            {{ row.conversation_title || `#${row.conversation_id}` }}
          </template>
        </el-table-column>
        <el-table-column prop="endpoint_kind" label="端点" width="88">
          <template #default="{ row }: { row: UsageRecordRow }">
            <el-tag :type="row.endpoint_kind === 'local' ? 'success' : 'info'" size="small">
              {{ row.endpoint_kind === "local" ? "本地" : "在线" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="对话模型" min-width="120" show-overflow-tooltip>
          <template #default="{ row }: { row: UsageRecordRow }">
            {{ row.model_display_name || "—" }}
          </template>
        </el-table-column>
        <el-table-column label="Emb" width="72" align="right">
          <template #default="{ row }: { row: UsageRecordRow }">
            {{ fmt(row.embed_prompt_tokens) }}
            <el-tag v-if="row.embed_is_estimated" size="small" type="warning" class="est">
              估
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Chat 入" width="88" align="right">
          <template #default="{ row }: { row: UsageRecordRow }">
            {{ fmt(row.chat_prompt_tokens) }}
          </template>
        </el-table-column>
        <el-table-column label="Chat 出" width="88" align="right">
          <template #default="{ row }: { row: UsageRecordRow }">
            {{ fmt(row.chat_completion_tokens) }}
            <el-tag v-if="row.chat_is_estimated" size="small" type="warning" class="est">
              估
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="合计" width="88" align="right">
          <template #default="{ row }: { row: UsageRecordRow }">
            {{ fmt(row.chat_total_tokens) }}
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="page"
        class="pager"
        :page-size="pageSize"
        :total="recordsTotal"
        layout="total, prev, pager, next"
        background
      />
    </el-card>
  </div>
</template>

<style scoped>
.usage-page {
  max-width: 1100px;
}
.page-head {
  margin-bottom: 20px;
}
.title {
  margin: 0 0 8px;
  font-size: 1.35rem;
  font-weight: 700;
  color: #0f172a;
}
.hint {
  margin: 0 0 16px;
  font-size: 13px;
  color: #64748b;
  line-height: 1.55;
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
  margin-bottom: 20px;
}
.card :deep(.el-card__header) {
  font-weight: 600;
  font-size: 14px;
}
.stat-line {
  margin-bottom: 12px;
}
.sub-stats {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: #64748b;
  margin-top: 6px;
}
.sub-stats strong {
  color: #0f172a;
}
.model-card {
  margin-bottom: 20px;
}
.table-card {
  margin-bottom: 24px;
}
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
.est {
  margin-left: 4px;
  vertical-align: middle;
}
</style>
