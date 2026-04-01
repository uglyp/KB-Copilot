<script setup lang="ts">
// 当前用户企业权限：与后端 PATCH /auth/me、GET /auth/me 对齐
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { useAclCatalogOptions } from "@/composables/useAclCatalogOptions";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const {
  branchSelectOptions,
  orgSelectOptions,
  deptSelectOptions,
  securitySelectOptions,
  fetchAcl,
} = useAclCatalogOptions();

const loading = ref(false);
const saving = ref(false);

const form = reactive({
  branch: "公共",
  role: "user",
  security_level: 4,
  departmentTags: [] as string[],
  org_id: "",
});

function fillFromUser() {
  const u = auth.user;
  if (!u) return;
  form.branch = u.branch;
  form.role = u.role;
  form.security_level = u.security_level;
  form.departmentTags = u.departments?.length ? [...u.departments] : [];
  form.org_id = u.org_id ?? "";
}

onMounted(async () => {
  loading.value = true;
  try {
    await fetchAcl();
    await auth.fetchMe();
    fillFromUser();
  } finally {
    loading.value = false;
  }
});

async function save() {
  if (!auth.user) return;
  saving.value = true;
  try {
    const parts = form.departmentTags.map((s) => String(s).trim()).filter(Boolean);
    await auth.patchMe({
      branch: form.branch.trim() || "公共",
      security_level: form.security_level,
      departments: parts.length ? parts : [],
      org_id: form.org_id.trim() || null,
    });
    ElMessage.success("已保存，令牌已刷新");
    fillFromUser();
  } catch {
    ElMessage.error("保存失败");
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <div class="account-page space-y-4">
    <p class="page-title">账户与权限</p>
    <p class="hint text-sm text-slate-500">
      选项与「系统管理」中的字典同步，可搜索或输入自定义值；分行、密级与部门用于 RAG
      可见范围，修改后将刷新令牌。组织 ID 与知识库「组织共享」一致时可协作。
    </p>

    <el-card v-loading="loading" class="max-w-xl" shadow="never">
      <el-form label-width="100px" @submit.prevent="save">
        <el-form-item label="用户名">
          <el-input :model-value="auth.user?.username" disabled />
        </el-form-item>
        <el-form-item label="分行 / 机构" required>
          <el-select
            v-model="form.branch"
            class="w-full"
            filterable
            allow-create
            default-first-option
            placeholder="选择或输入分行标签"
          >
            <el-option
              v-for="o in branchSelectOptions"
              :key="o.value"
              :label="o.label"
              :value="o.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="角色">
          <el-input :model-value="form.role" disabled placeholder="由管理员在系统管理中设置" />
        </el-form-item>
        <el-form-item label="密级上限">
          <el-select v-model="form.security_level" class="w-full">
            <el-option
              v-for="opt in securitySelectOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="所属部门">
          <el-select
            v-model="form.departmentTags"
            class="w-full"
            multiple
            filterable
            allow-create
            default-first-option
            collapse-tags
            collapse-tags-tooltip
            placeholder="多选字典部门或输入自定义编码"
          >
            <el-option
              v-for="o in deptSelectOptions"
              :key="o.value"
              :label="o.label"
              :value="o.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="组织 ID">
          <el-select
            v-model="form.org_id"
            class="w-full"
            filterable
            allow-create
            default-first-option
            clearable
            placeholder="选择或输入组织编码"
          >
            <el-option
              v-for="o in orgSelectOptions"
              :key="o.value"
              :label="o.label"
              :value="o.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" native-type="submit" :loading="saving">
            保存
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.page-title {
  font-size: 1.125rem;
  font-weight: 600;
  color: #0f172a;
}
.hint {
  max-width: 42rem;
  line-height: 1.5;
}
</style>
