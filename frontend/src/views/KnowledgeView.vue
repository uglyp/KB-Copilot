<script setup lang="ts">
// 知识库 CRUD + 文档上传列表（上传走 multipart，axios 会去掉 Content-Type 让浏览器带 boundary）
import { computed, onMounted, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import type { UploadFile } from "element-plus";
import type { AxiosError } from "axios";
import { Picture } from "@element-plus/icons-vue";
import { http } from "@/api/http";
import type { DocumentOut, KnowledgeBaseOut } from "@/api/types";
import AiMarkdown from "@/components/ai/AiMarkdown.vue";

type DocPreviewMode = "image" | "pdf" | "text" | "markdown";

const kbs = ref<KnowledgeBaseOut[]>([]);
const activeKbId = ref<number | null>(null);
const docs = ref<DocumentOut[]>([]);
const loading = ref(false);
const uploadLoading = ref(false);

const kbForm = ref({ name: "", description: "" });
const createKbVisible = ref(false);

const previewVisible = ref(false);
const previewLoading = ref(false);
const previewObjectUrl = ref<string | null>(null);
const previewTitle = ref("");
const previewMode = ref<DocPreviewMode | null>(null);
const previewTextContent = ref("");

const activeKb = computed(() => kbs.value.find((k) => k.id === activeKbId.value));

function revokePreviewUrl() {
  if (previewObjectUrl.value) {
    URL.revokeObjectURL(previewObjectUrl.value);
    previewObjectUrl.value = null;
  }
}

watch(previewVisible, (open) => {
  if (!open) {
    revokePreviewUrl();
    previewLoading.value = false;
    previewMode.value = null;
    previewTextContent.value = "";
  }
});

function getDocPreviewMode(row: DocumentOut): DocPreviewMode | null {
  if (row.modality === "image") return "image";
  if (row.modality !== "text") return null;
  const name = row.filename.toLowerCase();
  if (name.endsWith(".pdf")) return "pdf";
  if (name.endsWith(".md") || name.endsWith(".markdown")) return "markdown";
  if (name.endsWith(".txt")) return "text";
  return null;
}

async function openDocPreview(row: DocumentOut) {
  const mode = getDocPreviewMode(row);
  if (!mode || !activeKbId.value) return;
  revokePreviewUrl();
  previewTextContent.value = "";
  previewMode.value = mode;
  previewTitle.value = row.filename;
  previewVisible.value = true;
  previewLoading.value = true;
  const kbId = activeKbId.value;
  const docId = row.id;
  try {
    const { data } = await http.get<Blob>(
      `/knowledge-bases/${kbId}/documents/${docId}/file`,
      { responseType: "blob" }
    );
    if (!previewVisible.value) return;
    if (mode === "image" || mode === "pdf") {
      const blob =
        mode === "pdf" && (!data.type || !data.type.toLowerCase().includes("pdf"))
          ? new Blob([data], { type: "application/pdf" })
          : data;
      previewObjectUrl.value = URL.createObjectURL(blob);
    } else {
      previewTextContent.value = await data.text();
    }
  } catch {
    if (previewVisible.value) {
      ElMessage.error("文档预览加载失败");
      previewVisible.value = false;
    }
  } finally {
    previewLoading.value = false;
  }
}

async function loadKbs() {
  loading.value = true;
  try {
    const { data } = await http.get<KnowledgeBaseOut[]>("/knowledge-bases");
    kbs.value = data;
    if (!activeKbId.value && data.length) {
      activeKbId.value = data[0].id;
      await loadDocs();
    } else if (activeKbId.value) {
      await loadDocs();
    }
  } finally {
    loading.value = false;
  }
}

async function loadDocs() {
  if (!activeKbId.value) {
    docs.value = [];
    return;
  }
  const { data } = await http.get<DocumentOut[]>(
    `/knowledge-bases/${activeKbId.value}/documents`
  );
  docs.value = data;
}

async function createKb() {
  if (!kbForm.value.name.trim()) {
    ElMessage.warning("请填写知识库名称");
    return;
  }
  await http.post("/knowledge-bases", kbForm.value);
  ElMessage.success("已创建");
  createKbVisible.value = false;
  kbForm.value = { name: "", description: "" };
  await loadKbs();
}

async function onKbChange(id: number) {
  activeKbId.value = id;
  await loadDocs();
}

function handleKbSelect(index: string) {
  void onKbChange(Number(index));
}

async function onFileChange(uploadFile: UploadFile) {
  if (!activeKbId.value || !uploadFile.raw) return;
  uploadLoading.value = true;
  try {
    const fd = new FormData();
    fd.append("file", uploadFile.raw);
    await http.post(`/knowledge-bases/${activeKbId.value}/documents`, fd);
    ElMessage.success("已上传，后台处理中");
    await loadDocs();
  } catch (e: unknown) {
    const err = e as AxiosError<{ detail?: string | { message?: string } }>;
    const status = err.response?.status;
    if (status === 412) {
      ElMessage.error("请先完成向量/模型配置后再上传");
    } else {
      const d = err.response?.data?.detail;
      const msg =
        typeof d === "string"
          ? d
          : d && typeof d === "object" && "message" in d && d.message
            ? String(d.message)
            : err.message || "上传失败";
      ElMessage.error(msg);
    }
  } finally {
    uploadLoading.value = false;
  }
}

async function removeDoc(row: DocumentOut) {
  await ElMessageBox.confirm(`删除文档「${row.filename}」？`, "确认", {
    type: "warning",
  });
  await http.delete(`/knowledge-bases/${activeKbId.value}/documents/${row.id}`);
  ElMessage.success("已删除");
  await loadDocs();
}

onMounted(loadKbs);
</script>

<template>
  <div class="kb-page-shell space-y-4">
    <p class="kb-page-title">知识库</p>
    <div class="flex flex-wrap items-center gap-2">
      <el-button type="primary" class="!rounded-lg" round @click="createKbVisible = true">
        新建知识库
      </el-button>
    </div>

    <div class="grid gap-5 lg:grid-cols-12 lg:items-stretch">
      <aside
        class="flex min-h-[320px] flex-col overflow-hidden rounded-xl border border-border bg-card shadow-sm lg:col-span-5"
      >
        <div
          class="border-b border-border px-4 py-3 text-sm font-semibold text-foreground"
        >
          知识库列表
        </div>
        <div v-loading="loading" class="min-h-0 flex-1 overflow-auto p-2">
          <el-menu
            class="border-0 !bg-transparent"
            :default-active="String(activeKbId ?? '')"
            @select="handleKbSelect"
          >
            <el-menu-item v-for="k in kbs" :key="k.id" :index="String(k.id)">
              {{ k.name }}
            </el-menu-item>
          </el-menu>
          <el-empty v-if="!kbs.length" description="暂无知识库" />
        </div>
      </aside>

      <section
        class="flex min-h-[320px] flex-col overflow-hidden rounded-xl border border-border bg-card shadow-sm lg:col-span-7"
      >
        <div
          class="border-b border-border px-4 py-3 text-sm font-semibold text-foreground"
        >
          文档 — {{ activeKb?.name || "未选择" }}
        </div>
        <div class="flex min-h-0 flex-1 flex-col p-4">
          <div v-if="activeKbId" class="upload-row mb-3">
            <el-upload
              :auto-upload="false"
              :show-file-list="false"
              accept=".pdf,.txt,.md,.markdown,.png,.jpg,.jpeg,.webp,.gif,.bmp"
              @change="onFileChange"
            >
              <el-button type="primary" class="!rounded-lg" :loading="uploadLoading">
                上传文档或图片
              </el-button>
            </el-upload>
          </div>
          <el-table v-if="activeKbId" :data="docs" stripe class="kb-table w-full">
            <el-table-column prop="filename" label="文件名" min-width="200">
              <template #default="{ row }">
                <div class="kb-filename-cell">
                  <el-icon
                    v-if="row.modality === 'image'"
                    class="kb-filename-icon text-primary"
                    :title="'图像（OCR 入库）'"
                  >
                    <Picture />
                  </el-icon>
                  <span class="kb-filename-text">{{ row.filename }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="120" />
            <el-table-column label="错误" min-width="160">
              <template #default="{ row }">
                <span class="err">{{ row.error_message }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="148">
              <template #default="{ row }">
                <div class="kb-actions-cell">
                  <el-button
                    v-if="getDocPreviewMode(row)"
                    link
                    type="primary"
                    @click="openDocPreview(row)"
                  >
                    预览
                  </el-button>
                  <el-button link type="danger" @click="removeDoc(row)">删除</el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-else description="请选择左侧知识库" />
        </div>
      </section>
    </div>

    <el-dialog
      v-model="previewVisible"
      :title="previewTitle || '文档预览'"
      :width="previewMode === 'pdf' ? 'min(96vw, 960px)' : 'min(92vw, 800px)'"
      :class="[
        'kb-doc-preview-dialog',
        previewMode === 'pdf' ? 'kb-doc-preview-dialog--pdf' : '',
      ]"
      destroy-on-close
    >
      <div
        v-loading="previewLoading"
        :class="[
          'kb-preview-wrap min-h-[220px]',
          previewMode === 'pdf' ? 'kb-preview-wrap--pdf' : '',
        ]"
      >
        <el-image
          v-if="previewMode === 'image' && previewObjectUrl"
          :src="previewObjectUrl"
          fit="contain"
          class="kb-preview-image mx-auto flex max-h-[78vh] w-full justify-center"
          :preview-src-list="[previewObjectUrl]"
          preview-teleported
        />
        <iframe
          v-else-if="previewMode === 'pdf' && previewObjectUrl"
          class="kb-preview-pdf"
          :src="previewObjectUrl"
          title="PDF 预览"
        />
        <el-scrollbar
          v-else-if="previewMode === 'markdown' && previewTextContent !== ''"
          max-height="78vh"
          class="rounded-md border border-border bg-muted/30 px-4 py-3"
        >
          <AiMarkdown :content="previewTextContent" />
        </el-scrollbar>
        <el-scrollbar
          v-else-if="previewMode === 'text' && previewTextContent !== ''"
          max-height="78vh"
          class="rounded-md border border-border bg-muted/30"
        >
          <pre class="kb-preview-plain whitespace-pre-wrap break-words p-4 text-sm leading-relaxed">{{ previewTextContent }}</pre>
        </el-scrollbar>
      </div>
    </el-dialog>

    <el-dialog v-model="createKbVisible" title="新建知识库" width="420px">
      <el-form label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="kbForm.name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="kbForm.description" type="textarea" rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createKbVisible = false">取消</el-button>
        <el-button type="primary" @click="createKb">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.upload-row {
  margin-bottom: 0;
}
.err {
  color: var(--el-color-danger);
  font-size: 12px;
}

.kb-filename-cell {
  display: flex;
  align-items: flex-start;
  gap: 0.4rem;
  min-width: 0;
}

.kb-filename-icon {
  flex-shrink: 0;
  margin-top: 0.12rem;
  font-size: 1rem;
}

.kb-filename-text {
  min-width: 0;
  flex: 1;
  word-break: break-word;
  line-height: 1.45;
  font-size: 13px;
  color: hsl(var(--foreground));
}

.kb-actions-cell {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.125rem;
  white-space: nowrap;
}

.kb-preview-plain {
  margin: 0;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  color: hsl(var(--foreground));
}

/* PDF：尽量占满视口高度（扣除弹窗标题、内边距与默认上边距） */
.kb-preview-wrap--pdf {
  min-height: calc(100vh - 10.5rem);
}

.kb-preview-pdf {
  display: block;
  width: 100%;
  height: calc(100vh - 10.5rem);
  min-height: 36rem;
  border: 1px solid hsl(var(--border));
  border-radius: 0.375rem;
}

/* PDF 弹窗上移，少占顶部留白，给 iframe 更多可视高度 */
:deep(.kb-doc-preview-dialog--pdf) {
  margin-top: 5vh !important;
  margin-bottom: 2vh;
}
</style>
