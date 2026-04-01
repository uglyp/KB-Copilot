<script setup lang="ts">
// 注册成功后与登录相同：拿 token 再进应用；可选填企业权限（分行/密级/部门/组织，角色固定为 user）
import { onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { useAclCatalogOptions } from "@/composables/useAclCatalogOptions";
import { useAuthStore, type RegisterAclPayload } from "@/stores/auth";

const auth = useAuthStore();
const router = useRouter();
const {
  branchSelectOptions,
  orgSelectOptions,
  deptSelectOptions,
  securitySelectOptions,
  fetchAcl,
} = useAclCatalogOptions();

const form = reactive({ username: "", password: "", password2: "" });
const adv = reactive({
  branch: "",
  security_level: undefined as number | undefined,
  departmentTags: [] as string[],
  org_id: "",
});
const loading = ref(false);

onMounted(() => {
  void fetchAcl();
});

async function submit() {
  if (form.password !== form.password2) {
    ElMessage.warning("两次密码不一致");
    return;
  }
  loading.value = true;
  try {
    const acl: RegisterAclPayload = {};
    if (adv.branch.trim()) acl.branch = adv.branch.trim();
    if (adv.security_level != null) acl.security_level = adv.security_level;
    const deptParts = adv.departmentTags.map((s) => String(s).trim()).filter(Boolean);
    if (deptParts.length) acl.departments = deptParts;
    if (adv.org_id.trim()) acl.org_id = adv.org_id.trim();

    const hasAcl = Object.keys(acl).length > 0;
    await auth.register(form.username, form.password, hasAcl ? acl : undefined);
    await router.replace("/chat");
    ElMessage.success("注册成功");
  } catch {
    ElMessage.error("注册失败，用户名可能已被占用");
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="page">
    <el-card class="card" shadow="hover">
      <template #header>注册</template>
      <el-form :model="form" label-width="88px" @submit.prevent="submit">
        <el-form-item label="用户名">
          <el-input v-model="form.username" autocomplete="username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            autocomplete="new-password"
          />
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input
            v-model="form.password2"
            type="password"
            show-password
            autocomplete="new-password"
          />
        </el-form-item>

        <el-collapse class="reg-adv">
          <el-collapse-item title="企业权限（可选，与系统字典同步；注册后也可在「账户与权限」修改）" name="adv">
            <el-form-item label="分行">
              <el-select
                v-model="adv.branch"
                class="w-full"
                filterable
                allow-create
                default-first-option
                clearable
                placeholder="默认：公共"
              >
                <el-option
                  v-for="o in branchSelectOptions"
                  :key="o.value"
                  :label="o.label"
                  :value="o.value"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="密级上限">
              <el-select
                v-model="adv.security_level"
                clearable
                placeholder="默认：4"
                class="w-full"
              >
                <el-option
                  v-for="o in securitySelectOptions"
                  :key="o.value"
                  :label="o.label"
                  :value="o.value"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="部门">
              <el-select
                v-model="adv.departmentTags"
                class="w-full"
                multiple
                filterable
                allow-create
                default-first-option
                collapse-tags
                collapse-tags-tooltip
                placeholder="多选或自定义"
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
                v-model="adv.org_id"
                class="w-full"
                filterable
                allow-create
                default-first-option
                clearable
                placeholder="与共享知识库的组织编码一致"
              >
                <el-option
                  v-for="o in orgSelectOptions"
                  :key="o.value"
                  :label="o.label"
                  :value="o.value"
                />
              </el-select>
            </el-form-item>
          </el-collapse-item>
        </el-collapse>

        <el-form-item>
          <el-button type="primary" native-type="submit" :loading="loading">
            注册
          </el-button>
          <el-button @click="$router.push('/login')">已有账号</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(160deg, #f0f4ff 0%, #fff 50%);
  padding: 24px 16px;
}
.card {
  width: 100%;
  max-width: 440px;
}
.reg-adv {
  margin-bottom: 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
}
.reg-adv :deep(.el-collapse-item__header) {
  padding-left: 12px;
  font-size: 13px;
}
.reg-adv :deep(.el-collapse-item__content) {
  padding-bottom: 4px;
}
</style>
