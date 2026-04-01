<script setup lang="ts">
// 知识库 CRUD + 文档上传列表（上传走 multipart，axios 会去掉 Content-Type 让浏览器带 boundary）
import { computed, onMounted, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import type { UploadFile } from "element-plus";
import type { AxiosError } from "axios";
import { Picture } from "@element-plus/icons-vue";
import { http } from "@/api/http";
import type { DocumentOut, KnowledgeBaseOut } from "@/api/types";
import { useAclCatalogOptions } from "@/composables/useAclCatalogOptions";
import { useAuthStore } from "@/stores/auth";
import AiMarkdown from "@/components/ai/AiMarkdown.vue";

const auth = useAuthStore();
const {
  branchSelectOptions,
  orgSelectOptions,
  deptSelectOptions,
  securitySelectOptions,
  securityLabelMap,
  fetchAcl,
} = useAclCatalogOptions();

type DocPreviewMode = "image" | "pdf" | "text" | "markdown";

const kbs = ref<KnowledgeBaseOut[]>([]);
const activeKbId = ref<number | null>(null);
const docs = ref<DocumentOut[]>([]);
const loading = ref(false);
const uploadLoading = ref(false);

const kbForm = ref({
  name: "",
  description: "",
  org_id: "",
  is_org_shared: false,
});
const createKbVisible = ref(false);

const editKbVisible = ref(false);
const editKbSaving = ref(false);
const editKbId = ref<number | null>(null);
const editKbForm = ref({
  name: "",
  description: "",
  org_id: "",
  is_org_shared: false,
});

/** 上传文档时的权限元数据（与后端 Form 字段一致） */
const uploadAcl = ref({
  branch: "公共",
  security_level: 1,
  department: "",
});

const previewVisible = ref(false);
const previewLoading = ref(false);
const previewObjectUrl = ref<string | null>(null);
const previewTitle = ref("");
const previewMode = ref<DocPreviewMode | null>(null);
const previewTextContent = ref("");

const activeKb = computed(() => kbs.value.find((k) => k.id === activeKbId.value));

const editMetaVisible = ref(false);
const editMetaSaving = ref(false);
const editMetaForm = ref({
  branch: "公共",
  security_level: 1,
  department: "",
});
const editMetaDocId = ref<number | null>(null);
const editMetaFilename = ref("");

function canEditDocMetadata(row: DocumentOut): boolean {
  const me = auth.user?.id;
  if (me == null || !activeKb.value) return false;
  if (auth.isAdmin) return true;
  if (activeKb.value.user_id === me) return true;
  return row.creator_user_id != null && row.creator_user_id === me;
}

function openEditDocMetadata(row: DocumentOut) {
  if (!canEditDocMetadata(row)) return;
  editMetaDocId.value = row.id;
  editMetaFilename.value = row.filename;
  editMetaForm.value = {
    branch: row.branch || "公共",
    security_level: row.security_level,
    department: row.department ?? "",
  };
  editMetaVisible.value = true;
}

async function saveDocMetadata() {
  if (!activeKbId.value || editMetaDocId.value == null) return;
  editMetaSaving.value = true;
  try {
    await http.patch(
      `/knowledge-bases/${activeKbId.value}/documents/${editMetaDocId.value}`,
      {
        branch: (editMetaForm.value.branch || "").trim() || "公共",
        security_level: editMetaForm.value.security_level,
        department:
          typeof editMetaForm.value.department === "string"
            ? editMetaForm.value.department.trim() || null
            : null,
      },
    );
    ElMessage.success("已更新文档权限信息");
    editMetaVisible.value = false;
    await loadDocs();
  } catch (e: unknown) {
    const err = e as AxiosError<{ detail?: string }>;
    const d = err.response?.data?.detail;
    const msg = typeof d === "string" ? d : err.message || "保存失败";
    ElMessage.error(msg);
  } finally {
    editMetaSaving.value = false;
  }
}

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

function canManageKb(k: KnowledgeBaseOut): boolean {
  if (auth.user == null) return false;
  if (auth.isAdmin) return true;
  return k.user_id === auth.user.id;
}

function openEditKb(k: KnowledgeBaseOut) {
  if (!canManageKb(k)) return;
  editKbId.value = k.id;
  editKbForm.value = {
    name: k.name,
    description: k.description ?? "",
    org_id: k.org_id ?? "",
    is_org_shared: k.is_org_shared,
  };
  editKbVisible.value = true;
}

async function saveKbEdit() {
  if (editKbId.value == null) return;
  const nm = editKbForm.value.name.trim();
  if (!nm) {
    ElMessage.warning("请填写知识库名称");
    return;
  }
  editKbSaving.value = true;
  try {
    await http.patch(`/knowledge-bases/${editKbId.value}`, {
      name: nm,
      description: editKbForm.value.description.trim() || null,
      org_id: (editKbForm.value.org_id || "").trim() || null,
      is_org_shared: editKbForm.value.is_org_shared,
    });
    ElMessage.success("已保存");
    editKbVisible.value = false;
    await loadKbs();
  } catch (e: unknown) {
    const err = e as AxiosError<{ detail?: string }>;
    const d = err.response?.data?.detail;
    ElMessage.error(typeof d === "string" ? d : err.message || "保存失败");
  } finally {
    editKbSaving.value = false;
  }
}

async function removeKb(k: KnowledgeBaseOut) {
  if (!canManageKb(k)) return;
  await ElMessageBox.confirm(
    `删除知识库「${k.name}」将移除其中全部文档、会话与向量数据，不可恢复。确定？`,
    "确认删除",
    { type: "warning" },
  );
  const wasActive = activeKbId.value === k.id;
  await http.delete(`/knowledge-bases/${k.id}`);
  ElMessage.success("已删除");
  if (wasActive) activeKbId.value = null;
  await loadKbs();
  if (wasActive && kbs.value.length) {
    activeKbId.value = kbs.value[0].id;
    await loadDocs();
  } else {
    docs.value = [];
  }
}

async function createKb() {
  if (!kbForm.value.name.trim()) {
    ElMessage.warning("请填写知识库名称");
    return;
  }
  const oid = (kbForm.value.org_id || "").trim();
  await http.post("/knowledge-bases", {
    name: kbForm.value.name.trim(),
    description: kbForm.value.description.trim() || null,
    org_id: oid || null,
    is_org_shared: kbForm.value.is_org_shared,
  });
  ElMessage.success("已创建");
  createKbVisible.value = false;
  kbForm.value = {
    name: "",
    description: "",
    org_id: "",
    is_org_shared: false,
  };
  await loadKbs();
}

async function onKbChange(id: number) {
  activeKbId.value = id;
  await loadDocs();
}

async function onFileChange(uploadFile: UploadFile) {
  if (!activeKbId.value || !uploadFile.raw) return;
  uploadLoading.value = true;
  try {
    const fd = new FormData();
    fd.append("file", uploadFile.raw);
    fd.append("branch", (uploadAcl.value.branch || "").trim() || "公共");
    fd.append("security_level", String(uploadAcl.value.security_level));
    const deptRaw = uploadAcl.value.department;
    const dept = typeof deptRaw === "string" ? deptRaw.trim() : "";
    if (dept) fd.append("department", dept);
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

onMounted(async () => {
  await fetchAcl();
  await loadKbs();
});
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
          <div v-if="kbs.length" class="kb-side-list space-y-1">
            <div
              v-for="k in kbs"
              :key="k.id"
              class="kb-side-row"
              :class="{ 'kb-side-row--active': k.id === activeKbId }"
            >
              <button
                type="button"
                class="kb-side-row-main"
                @click="onKbChange(k.id)"
              >
                <span class="kb-menu-label">{{ k.name }}</span>
                <el-tag
                  v-if="k.is_org_shared"
                  size="small"
                  type="info"
                  class="!ml-1 !align-middle"
                >
                  组织共享
                </el-tag>
              </button>
              <div v-if="canManageKb(k)" class="kb-side-row-actions" @click.stop>
                <el-button link type="primary" size="small" @click="openEditKb(k)">
                  编辑
                </el-button>
                <el-button link type="danger" size="small" @click="removeKb(k)">
                  删除
                </el-button>
              </div>
            </div>
          </div>
          <el-empty v-else description="暂无知识库" />
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
          <div v-if="activeKbId" class="upload-block mb-3 space-y-2">
            <el-collapse class="upload-acl-collapse">
              <el-collapse-item title="上传时的文档权限（可选）" name="acl">
                <el-form :model="uploadAcl" label-width="88px" size="small">
                  <div class="grid gap-1 sm:grid-cols-2">
                    <el-form-item label="分行标签" class="!mb-2">
                      <el-select
                        v-model="uploadAcl.branch"
                        class="w-full"
                        filterable
                        allow-create
                        default-first-option
                        placeholder="默认「公共」"
                      >
                        <el-option
                          v-for="o in branchSelectOptions"
                          :key="o.value"
                          :label="o.label"
                          :value="o.value"
                        />
                      </el-select>
                    </el-form-item>
                    <el-form-item label="密级" class="!mb-2">
                      <el-select v-model="uploadAcl.security_level" class="w-full">
                        <el-option
                          v-for="o in securitySelectOptions"
                          :key="o.value"
                          :label="o.label"
                          :value="o.value"
                        />
                      </el-select>
                    </el-form-item>
                    <el-form-item label="限定部门" class="!mb-0 sm:col-span-2">
                      <el-select
                        v-model="uploadAcl.department"
                        class="w-full"
                        filterable
                        allow-create
                        default-first-option
                        clearable
                        placeholder="留空不限；可选字典或自定义"
                      >
                        <el-option
                          v-for="o in deptSelectOptions"
                          :key="o.value"
                          :label="o.label"
                          :value="o.value"
                        />
                      </el-select>
                    </el-form-item>
                  </div>
                </el-form>
              </el-collapse-item>
            </el-collapse>
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
            <el-table-column prop="branch" label="分行" width="100" show-overflow-tooltip />
            <el-table-column label="密级" width="72">
              <template #default="{ row }">
                {{ securityLabelMap[row.security_level] ?? row.security_level }}
              </template>
            </el-table-column>
            <el-table-column
              prop="department"
              label="部门"
              width="100"
              show-overflow-tooltip
            />
            <el-table-column prop="status" label="状态" width="120" />
            <el-table-column label="错误" min-width="160">
              <template #default="{ row }">
                <span class="err">{{ row.error_message }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="220">
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
                  <el-button
                    v-if="canEditDocMetadata(row)"
                    link
                    type="primary"
                    @click="openEditDocMetadata(row)"
                  >
                    编辑权限
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

    <el-dialog
      v-model="editMetaVisible"
      :title="`编辑文档权限 — ${editMetaFilename}`"
      width="480px"
      destroy-on-close
    >
      <el-form :model="editMetaForm" label-width="88px">
        <el-form-item label="分行标签">
          <el-select
            v-model="editMetaForm.branch"
            class="w-full"
            filterable
            allow-create
            default-first-option
            placeholder="默认「公共」"
          >
            <el-option
              v-for="o in branchSelectOptions"
              :key="o.value"
              :label="o.label"
              :value="o.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="密级">
          <el-select v-model="editMetaForm.security_level" class="w-full">
            <el-option
              v-for="o in securitySelectOptions"
              :key="o.value"
              :label="o.label"
              :value="o.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="限定部门">
          <el-select
            v-model="editMetaForm.department"
            class="w-full"
            filterable
            allow-create
            default-first-option
            clearable
            placeholder="留空表示不限"
          >
            <el-option
              v-for="o in deptSelectOptions"
              :key="o.value"
              :label="o.label"
              :value="o.value"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editMetaVisible = false">取消</el-button>
        <el-button type="primary" :loading="editMetaSaving" @click="saveDocMetadata">
          保存
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="editKbVisible"
      title="编辑知识库"
      width="480px"
      destroy-on-close
    >
      <el-form label-width="108px">
        <el-form-item label="名称" required>
          <el-input v-model="editKbForm.name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="editKbForm.description" type="textarea" rows="3" />
        </el-form-item>
        <el-form-item label="组织 ID">
          <el-select
            v-model="editKbForm.org_id"
            class="w-full"
            filterable
            allow-create
            default-first-option
            clearable
            placeholder="与成员「组织 ID」一致时可共享"
          >
            <el-option
              v-for="o in orgSelectOptions"
              :key="o.value"
              :label="o.label"
              :value="o.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="组织共享">
          <el-switch v-model="editKbForm.is_org_shared" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editKbVisible = false">取消</el-button>
        <el-button type="primary" :loading="editKbSaving" @click="saveKbEdit">
          保存
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="createKbVisible" title="新建知识库" width="480px">
      <el-form label-width="108px">
        <el-form-item label="名称">
          <el-input v-model="kbForm.name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="kbForm.description" type="textarea" rows="3" />
        </el-form-item>
        <el-form-item label="组织 ID">
          <el-select
            v-model="kbForm.org_id"
            class="w-full"
            filterable
            allow-create
            default-first-option
            clearable
            placeholder="与成员「组织 ID」一致时可共享"
          >
            <el-option
              v-for="o in orgSelectOptions"
              :key="o.value"
              :label="o.label"
              :value="o.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="组织共享">
          <el-switch v-model="kbForm.is_org_shared" />
          <span class="ml-2 text-xs text-slate-500">开启后同组织用户可访问本库</span>
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
.upload-block {
  margin-bottom: 0;
}
.upload-acl-collapse {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 0.5rem;
  overflow: hidden;
}
.upload-acl-collapse :deep(.el-collapse-item__header) {
  padding-left: 12px;
  font-size: 13px;
}
.upload-acl-collapse :deep(.el-collapse-item__content) {
  padding: 12px;
}
.kb-menu-label {
  vertical-align: middle;
}

.kb-side-list {
  display: flex;
  flex-direction: column;
}

.kb-side-row {
  display: flex;
  align-items: center;
  gap: 4px;
  border-radius: 0.5rem;
  border: 1px solid transparent;
  padding: 2px 4px 2px 2px;
}

.kb-side-row--active {
  background: hsl(var(--muted) / 0.45);
  border-color: hsl(var(--border));
}

.kb-side-row-main {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
  padding: 8px 10px;
  text-align: left;
  border: none;
  background: transparent;
  cursor: pointer;
  font: inherit;
  color: hsl(var(--foreground));
  border-radius: 0.375rem;
}

.kb-side-row-main:hover {
  background: hsl(var(--muted) / 0.25);
}

.kb-side-row-actions {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 0;
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
