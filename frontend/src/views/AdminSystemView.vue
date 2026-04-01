<script setup lang="ts">
/**
 * 系统管理：用户、组织、分行、部门、角色、密级字典（需 role=admin）
 */
import { onMounted, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import type { AxiosError } from "axios";
import { http } from "@/api/http";
import type {
  AdminUserOut,
  SysBranchOut,
  SysDepartmentOut,
  SysOrganizationOut,
  SysRoleOut,
  SysSecurityLevelOut,
} from "@/api/types";
import { useAclCatalogOptions } from "@/composables/useAclCatalogOptions";
import { useAclCatalogStore } from "@/stores/aclCatalog";

const aclCatalogStore = useAclCatalogStore();
const {
  branchSelectOptions,
  orgSelectOptions,
  deptSelectOptions,
  securitySelectOptions,
  fetchAcl,
} = useAclCatalogOptions();

const tab = ref<
  "users" | "organizations" | "branches" | "departments" | "roles" | "security-levels"
>("users");
const loading = ref(false);

function errMsg(e: unknown): string {
  const err = e as AxiosError<{ detail?: string }>;
  const d = err.response?.data?.detail;
  return typeof d === "string" ? d : err.message || "操作失败";
}

// —— 用户 ——
const users = ref<AdminUserOut[]>([]);
const userDialog = ref(false);
const userSaving = ref(false);
const userIsCreate = ref(true);
const userForm = ref({
  id: 0,
  username: "",
  password: "",
  branch: "公共",
  role: "user",
  security_level: 4,
  org_id: "",
  departmentTags: [] as string[],
  is_active: true,
  new_password: "",
});

async function loadUsers() {
  const { data } = await http.get<AdminUserOut[]>("/admin/users");
  users.value = data;
}

function openCreateUser() {
  userIsCreate.value = true;
  userForm.value = {
    id: 0,
    username: "",
    password: "",
    branch: "公共",
    role: "user",
    security_level: 4,
    org_id: "",
    departmentTags: [],
    is_active: true,
    new_password: "",
  };
  userDialog.value = true;
}

function openEditUser(row: AdminUserOut) {
  userIsCreate.value = false;
  userForm.value = {
    id: row.id,
    username: row.username,
    password: "",
    branch: row.branch,
    role: row.role,
    security_level: row.security_level,
    org_id: row.org_id ?? "",
    departmentTags: row.departments?.length ? [...row.departments] : [],
    is_active: row.is_active,
    new_password: "",
  };
  userDialog.value = true;
}

async function saveUser() {
  userSaving.value = true;
  try {
    const parts = userForm.value.departmentTags.map((s) => String(s).trim()).filter(Boolean);
    if (userIsCreate.value) {
      if (!userForm.value.username.trim()) {
        ElMessage.warning("请填写用户名");
        return;
      }
      if (!userForm.value.password || userForm.value.password.length < 6) {
        ElMessage.warning("密码至少 6 位");
        return;
      }
      await http.post("/admin/users", {
        username: userForm.value.username.trim(),
        password: userForm.value.password,
        branch: (userForm.value.branch || "").trim() || "公共",
        role: userForm.value.role.trim() || "user",
        security_level: userForm.value.security_level,
        org_id: (userForm.value.org_id || "").trim() || null,
        departments: parts.length ? parts : [],
        is_active: userForm.value.is_active,
      });
      ElMessage.success("已创建用户");
    } else {
      const body: Record<string, unknown> = {
        branch: (userForm.value.branch || "").trim() || "公共",
        role: userForm.value.role.trim() || "user",
        security_level: userForm.value.security_level,
        org_id: (userForm.value.org_id || "").trim() || null,
        departments: parts.length ? parts : [],
        is_active: userForm.value.is_active,
      };
      if (userForm.value.new_password.trim().length >= 6) {
        body.new_password = userForm.value.new_password.trim();
      }
      await http.patch(`/admin/users/${userForm.value.id}`, body);
      ElMessage.success("已保存");
    }
    userDialog.value = false;
    await loadUsers();
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    userSaving.value = false;
  }
}

async function removeUser(row: AdminUserOut) {
  await ElMessageBox.confirm(`确定删除用户「${row.username}」？将清理其知识库与相关数据。`, "确认", {
    type: "warning",
  });
  try {
    await http.delete(`/admin/users/${row.id}`);
    ElMessage.success("已删除");
    await loadUsers();
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

// —— 组织 ——
const orgs = ref<SysOrganizationOut[]>([]);
const orgDialog = ref(false);
const orgSaving = ref(false);
const orgForm = ref({ id: 0, org_code: "", name: "", description: "", enabled: true });

async function loadOrgs() {
  const { data } = await http.get<SysOrganizationOut[]>("/admin/organizations");
  orgs.value = data;
}

function openOrgCreate() {
  orgForm.value = { id: 0, org_code: "", name: "", description: "", enabled: true };
  orgDialog.value = true;
}

function openOrgEdit(row: SysOrganizationOut) {
  orgForm.value = {
    id: row.id,
    org_code: row.org_code,
    name: row.name,
    description: row.description ?? "",
    enabled: row.enabled,
  };
  orgDialog.value = true;
}

async function saveOrg() {
  orgSaving.value = true;
  try {
    if (!orgForm.value.org_code.trim() || !orgForm.value.name.trim()) {
      ElMessage.warning("请填写组织编码与名称");
      return;
    }
    if (orgForm.value.id) {
      await http.patch(`/admin/organizations/${orgForm.value.id}`, {
        org_code: orgForm.value.org_code.trim(),
        name: orgForm.value.name.trim(),
        description: orgForm.value.description.trim() || null,
        enabled: orgForm.value.enabled,
      });
    } else {
      await http.post("/admin/organizations", {
        org_code: orgForm.value.org_code.trim(),
        name: orgForm.value.name.trim(),
        description: orgForm.value.description.trim() || null,
        enabled: orgForm.value.enabled,
      });
    }
    ElMessage.success("已保存");
    aclCatalogStore.invalidate();
    orgDialog.value = false;
    await loadOrgs();
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    orgSaving.value = false;
  }
}

async function removeOrg(row: SysOrganizationOut) {
  await ElMessageBox.confirm(`删除组织「${row.name}」？`, "确认", { type: "warning" });
  try {
    await http.delete(`/admin/organizations/${row.id}`);
    ElMessage.success("已删除");
    aclCatalogStore.invalidate();
    await loadOrgs();
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

// —— 分行 ——
const branches = ref<SysBranchOut[]>([]);
const branchDialog = ref(false);
const branchSaving = ref(false);
const branchForm = ref({ id: 0, code: "", name: "", sort_order: 0, enabled: true });

async function loadBranches() {
  const { data } = await http.get<SysBranchOut[]>("/admin/branches");
  branches.value = data;
}

function openBranchCreate() {
  branchForm.value = { id: 0, code: "", name: "", sort_order: 0, enabled: true };
  branchDialog.value = true;
}

function openBranchEdit(row: SysBranchOut) {
  branchForm.value = {
    id: row.id,
    code: row.code,
    name: row.name,
    sort_order: row.sort_order,
    enabled: row.enabled,
  };
  branchDialog.value = true;
}

async function saveBranch() {
  branchSaving.value = true;
  try {
    if (!branchForm.value.code.trim() || !branchForm.value.name.trim()) {
      ElMessage.warning("请填写编码与名称");
      return;
    }
    if (branchForm.value.id) {
      await http.patch(`/admin/branches/${branchForm.value.id}`, {
        code: branchForm.value.code.trim(),
        name: branchForm.value.name.trim(),
        sort_order: branchForm.value.sort_order,
        enabled: branchForm.value.enabled,
      });
    } else {
      await http.post("/admin/branches", {
        code: branchForm.value.code.trim(),
        name: branchForm.value.name.trim(),
        sort_order: branchForm.value.sort_order,
        enabled: branchForm.value.enabled,
      });
    }
    ElMessage.success("已保存");
    aclCatalogStore.invalidate();
    branchDialog.value = false;
    await loadBranches();
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    branchSaving.value = false;
  }
}

async function removeBranch(row: SysBranchOut) {
  await ElMessageBox.confirm(`删除分行「${row.name}」？`, "确认", { type: "warning" });
  try {
    await http.delete(`/admin/branches/${row.id}`);
    ElMessage.success("已删除");
    aclCatalogStore.invalidate();
    await loadBranches();
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

// —— 部门 ——
const depts = ref<SysDepartmentOut[]>([]);
const deptDialog = ref(false);
const deptSaving = ref(false);
const deptForm = ref({ id: 0, code: "", name: "", org_code: "", enabled: true });

async function loadDepts() {
  const { data } = await http.get<SysDepartmentOut[]>("/admin/departments");
  depts.value = data;
}

function openDeptCreate() {
  deptForm.value = { id: 0, code: "", name: "", org_code: "", enabled: true };
  deptDialog.value = true;
}

function openDeptEdit(row: SysDepartmentOut) {
  deptForm.value = {
    id: row.id,
    code: row.code,
    name: row.name,
    org_code: row.org_code ?? "",
    enabled: row.enabled,
  };
  deptDialog.value = true;
}

async function saveDept() {
  deptSaving.value = true;
  try {
    if (!deptForm.value.code.trim() || !deptForm.value.name.trim()) {
      ElMessage.warning("请填写部门编码与名称");
      return;
    }
    const oc = deptForm.value.org_code.trim() || null;
    if (deptForm.value.id) {
      await http.patch(`/admin/departments/${deptForm.value.id}`, {
        code: deptForm.value.code.trim(),
        name: deptForm.value.name.trim(),
        org_code: oc,
        enabled: deptForm.value.enabled,
      });
    } else {
      await http.post("/admin/departments", {
        code: deptForm.value.code.trim(),
        name: deptForm.value.name.trim(),
        org_code: oc,
        enabled: deptForm.value.enabled,
      });
    }
    ElMessage.success("已保存");
    aclCatalogStore.invalidate();
    deptDialog.value = false;
    await loadDepts();
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    deptSaving.value = false;
  }
}

async function removeDept(row: SysDepartmentOut) {
  await ElMessageBox.confirm(`删除部门「${row.name}」？`, "确认", { type: "warning" });
  try {
    await http.delete(`/admin/departments/${row.id}`);
    ElMessage.success("已删除");
    aclCatalogStore.invalidate();
    await loadDepts();
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

// —— 角色 ——
const roles = ref<SysRoleOut[]>([]);
const roleDialog = ref(false);
const roleSaving = ref(false);
const roleForm = ref({ id: 0, code: "", display_name: "", description: "", enabled: true });

async function loadRoles() {
  const { data } = await http.get<SysRoleOut[]>("/admin/roles");
  roles.value = data;
}

function openRoleCreate() {
  roleForm.value = { id: 0, code: "", display_name: "", description: "", enabled: true };
  roleDialog.value = true;
}

function openRoleEdit(row: SysRoleOut) {
  roleForm.value = {
    id: row.id,
    code: row.code,
    display_name: row.display_name,
    description: row.description ?? "",
    enabled: row.enabled,
  };
  roleDialog.value = true;
}

async function saveRole() {
  roleSaving.value = true;
  try {
    if (!roleForm.value.code.trim() || !roleForm.value.display_name.trim()) {
      ElMessage.warning("请填写角色编码与显示名");
      return;
    }
    if (roleForm.value.id) {
      await http.patch(`/admin/roles/${roleForm.value.id}`, {
        code: roleForm.value.code.trim(),
        display_name: roleForm.value.display_name.trim(),
        description: roleForm.value.description.trim() || null,
        enabled: roleForm.value.enabled,
      });
    } else {
      await http.post("/admin/roles", {
        code: roleForm.value.code.trim(),
        display_name: roleForm.value.display_name.trim(),
        description: roleForm.value.description.trim() || null,
        enabled: roleForm.value.enabled,
      });
    }
    ElMessage.success("已保存");
    roleDialog.value = false;
    await loadRoles();
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    roleSaving.value = false;
  }
}

async function removeRole(row: SysRoleOut) {
  await ElMessageBox.confirm(`删除角色「${row.display_name}」？`, "确认", { type: "warning" });
  try {
    await http.delete(`/admin/roles/${row.id}`);
    ElMessage.success("已删除");
    await loadRoles();
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

// —— 密级 ——
const secLevels = ref<SysSecurityLevelOut[]>([]);
const secDialog = ref(false);
const secSaving = ref(false);
const secForm = ref({ level: 1, label: "", description: "", sort_order: 0 });

async function loadSecLevels() {
  const { data } = await http.get<SysSecurityLevelOut[]>("/admin/security-levels");
  secLevels.value = data;
}

function openSecEdit(row: SysSecurityLevelOut) {
  secForm.value = {
    level: row.level,
    label: row.label,
    description: row.description ?? "",
    sort_order: row.sort_order,
  };
  secDialog.value = true;
}

async function saveSec() {
  secSaving.value = true;
  try {
    if (!secForm.value.label.trim()) {
      ElMessage.warning("请填写密级名称");
      return;
    }
    await http.patch(`/admin/security-levels/${secForm.value.level}`, {
      label: secForm.value.label.trim(),
      description: secForm.value.description.trim() || null,
      sort_order: secForm.value.sort_order,
    });
    ElMessage.success("已保存");
    aclCatalogStore.invalidate();
    secDialog.value = false;
    await loadSecLevels();
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    secSaving.value = false;
  }
}

async function loadTab() {
  loading.value = true;
  try {
    switch (tab.value) {
      case "users":
        await loadUsers();
        break;
      case "organizations":
        await loadOrgs();
        break;
      case "branches":
        await loadBranches();
        break;
      case "departments":
        await loadDepts();
        break;
      case "roles":
        await loadRoles();
        break;
      case "security-levels":
        await loadSecLevels();
        break;
    }
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

watch(tab, () => {
  void loadTab();
});

onMounted(async () => {
  await fetchAcl();
  await loadTab();
});
</script>

<template>
  <div class="admin-page space-y-4">
    <p class="page-title">系统管理</p>
    <p class="hint text-sm text-slate-500">
      维护用户账号与权限字典（分行/组织/部门/角色/密级展示名）。业务 ACL 仍使用用户与文档上的字符串与密级数值。
    </p>

    <el-card shadow="never" v-loading="loading">
      <el-tabs v-model="tab">
        <el-tab-pane label="用户" name="users">
          <div class="mb-3">
            <el-button type="primary" @click="openCreateUser">新建用户</el-button>
          </div>
          <el-table :data="users" stripe size="small">
            <el-table-column prop="id" label="ID" width="64" />
            <el-table-column prop="username" label="用户名" min-width="100" />
            <el-table-column prop="branch" label="分行" width="120" show-overflow-tooltip />
            <el-table-column prop="role" label="角色" width="100" />
            <el-table-column prop="security_level" label="密级上限" width="88" />
            <el-table-column prop="org_id" label="组织 ID" width="120" show-overflow-tooltip />
            <el-table-column label="启用" width="72">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
                  {{ row.is_active ? "是" : "否" }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="160" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="openEditUser(row)">编辑</el-button>
                <el-button link type="danger" @click="removeUser(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="组织" name="organizations">
          <div class="mb-3">
            <el-button type="primary" @click="openOrgCreate">新建组织</el-button>
          </div>
          <el-table :data="orgs" stripe size="small">
            <el-table-column prop="org_code" label="组织编码" width="140" />
            <el-table-column prop="name" label="名称" min-width="140" />
            <el-table-column prop="description" label="说明" min-width="160" show-overflow-tooltip />
            <el-table-column label="启用" width="72">
              <template #default="{ row }">
                {{ row.enabled ? "是" : "否" }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="160" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="openOrgEdit(row)">编辑</el-button>
                <el-button link type="danger" @click="removeOrg(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="分行/机构" name="branches">
          <div class="mb-3">
            <el-button type="primary" @click="openBranchCreate">新建分行</el-button>
          </div>
          <el-table :data="branches" stripe size="small">
            <el-table-column prop="code" label="编码" width="140" />
            <el-table-column prop="name" label="名称" min-width="140" />
            <el-table-column prop="sort_order" label="排序" width="72" />
            <el-table-column label="启用" width="72">
              <template #default="{ row }">
                {{ row.enabled ? "是" : "否" }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="160" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="openBranchEdit(row)">编辑</el-button>
                <el-button link type="danger" @click="removeBranch(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="部门" name="departments">
          <div class="mb-3">
            <el-button type="primary" @click="openDeptCreate">新建部门</el-button>
          </div>
          <el-table :data="depts" stripe size="small">
            <el-table-column prop="code" label="编码" width="140" />
            <el-table-column prop="name" label="名称" min-width="140" />
            <el-table-column prop="org_code" label="所属组织编码" width="140" show-overflow-tooltip />
            <el-table-column label="启用" width="72">
              <template #default="{ row }">
                {{ row.enabled ? "是" : "否" }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="160" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="openDeptEdit(row)">编辑</el-button>
                <el-button link type="danger" @click="removeDept(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="角色" name="roles">
          <div class="mb-3">
            <el-button type="primary" @click="openRoleCreate">新建角色</el-button>
          </div>
          <el-table :data="roles" stripe size="small">
            <el-table-column prop="code" label="编码" width="120" />
            <el-table-column prop="display_name" label="显示名" min-width="120" />
            <el-table-column prop="description" label="说明" min-width="160" show-overflow-tooltip />
            <el-table-column label="启用" width="72">
              <template #default="{ row }">
                {{ row.enabled ? "是" : "否" }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="160" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="openRoleEdit(row)">编辑</el-button>
                <el-button link type="danger" @click="removeRole(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="密级" name="security-levels">
          <el-table :data="secLevels" stripe size="small">
            <el-table-column prop="level" label="级别" width="72" />
            <el-table-column prop="label" label="名称" width="120" />
            <el-table-column prop="description" label="说明" min-width="200" show-overflow-tooltip />
            <el-table-column prop="sort_order" label="排序" width="72" />
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="openSecEdit(row)">编辑</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 用户 -->
    <el-dialog
      v-model="userDialog"
      :title="userIsCreate ? '新建用户' : `编辑用户 — ${userForm.username}`"
      width="520px"
      destroy-on-close
    >
      <el-form label-width="108px">
        <el-form-item v-if="userIsCreate" label="用户名" required>
          <el-input v-model="userForm.username" autocomplete="off" />
        </el-form-item>
        <el-form-item v-if="userIsCreate" label="密码" required>
          <el-input v-model="userForm.password" type="password" show-password autocomplete="new-password" />
        </el-form-item>
        <el-form-item v-if="!userIsCreate" label="重置密码">
          <el-input
            v-model="userForm.new_password"
            type="password"
            show-password
            placeholder="留空则不修改"
            autocomplete="new-password"
          />
        </el-form-item>
        <el-form-item label="分行">
          <el-select
            v-model="userForm.branch"
            class="w-full"
            filterable
            allow-create
            default-first-option
            placeholder="选择或输入"
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
          <el-input v-model="userForm.role" placeholder="如 user / admin" />
        </el-form-item>
        <el-form-item label="密级上限">
          <el-select v-model="userForm.security_level" class="w-full">
            <el-option
              v-for="o in securitySelectOptions"
              :key="o.value"
              :label="o.label"
              :value="o.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="组织 ID">
          <el-select
            v-model="userForm.org_id"
            class="w-full"
            filterable
            allow-create
            default-first-option
            clearable
            placeholder="选择或输入"
          >
            <el-option
              v-for="o in orgSelectOptions"
              :key="o.value"
              :label="o.label"
              :value="o.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="部门">
          <el-select
            v-model="userForm.departmentTags"
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
        <el-form-item label="启用">
          <el-switch v-model="userForm.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="userDialog = false">取消</el-button>
        <el-button type="primary" :loading="userSaving" @click="saveUser">保存</el-button>
      </template>
    </el-dialog>

    <!-- 组织 -->
    <el-dialog v-model="orgDialog" title="组织" width="480px" destroy-on-close>
      <el-form label-width="100px">
        <el-form-item label="组织编码" required>
          <el-input v-model="orgForm.org_code" />
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="orgForm.name" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="orgForm.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="orgForm.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="orgDialog = false">取消</el-button>
        <el-button type="primary" :loading="orgSaving" @click="saveOrg">保存</el-button>
      </template>
    </el-dialog>

    <!-- 分行 -->
    <el-dialog v-model="branchDialog" title="分行/机构" width="480px" destroy-on-close>
      <el-form label-width="88px">
        <el-form-item label="编码" required>
          <el-input v-model="branchForm.code" />
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="branchForm.name" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="branchForm.sort_order" :min="0" class="w-full" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="branchForm.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="branchDialog = false">取消</el-button>
        <el-button type="primary" :loading="branchSaving" @click="saveBranch">保存</el-button>
      </template>
    </el-dialog>

    <!-- 部门 -->
    <el-dialog v-model="deptDialog" title="部门" width="480px" destroy-on-close>
      <el-form label-width="108px">
        <el-form-item label="部门编码" required>
          <el-input v-model="deptForm.code" />
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="deptForm.name" />
        </el-form-item>
        <el-form-item label="组织编码">
          <el-input v-model="deptForm.org_code" placeholder="可选" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="deptForm.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="deptDialog = false">取消</el-button>
        <el-button type="primary" :loading="deptSaving" @click="saveDept">保存</el-button>
      </template>
    </el-dialog>

    <!-- 角色 -->
    <el-dialog v-model="roleDialog" title="角色" width="480px" destroy-on-close>
      <el-form label-width="88px">
        <el-form-item label="编码" required>
          <el-input v-model="roleForm.code" />
        </el-form-item>
        <el-form-item label="显示名" required>
          <el-input v-model="roleForm.display_name" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="roleForm.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="roleForm.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="roleDialog = false">取消</el-button>
        <el-button type="primary" :loading="roleSaving" @click="saveRole">保存</el-button>
      </template>
    </el-dialog>

    <!-- 密级 -->
    <el-dialog v-model="secDialog" :title="`编辑密级 — ${secForm.level}`" width="480px" destroy-on-close>
      <el-form label-width="88px">
        <el-form-item label="名称" required>
          <el-input v-model="secForm.label" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="secForm.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="secForm.sort_order" :min="0" class="w-full" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="secDialog = false">取消</el-button>
        <el-button type="primary" :loading="secSaving" @click="saveSec">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-title {
  font-size: 1.25rem;
  font-weight: 600;
  color: #0f172a;
}
</style>
