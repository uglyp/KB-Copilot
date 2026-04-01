import { defineStore } from "pinia";
import { ref } from "vue";
import { http } from "@/api/http";
import type { AclCatalogOut } from "@/api/types";

/** 系统管理维护的 ACL 字典缓存；注册页无 token 也可请求 /acl-catalog */
export const useAclCatalogStore = defineStore("aclCatalog", () => {
  const loading = ref(false);
  const loaded = ref(false);
  const branches = ref<AclCatalogOut["branches"]>([]);
  const organizations = ref<AclCatalogOut["organizations"]>([]);
  const departments = ref<AclCatalogOut["departments"]>([]);
  const security_levels = ref<AclCatalogOut["security_levels"]>([]);

  function invalidate() {
    loaded.value = false;
  }

  async function fetchCatalog(force = false) {
    if (loaded.value && !force) return;
    loading.value = true;
    try {
      const { data } = await http.get<AclCatalogOut>("/acl-catalog");
      branches.value = data.branches ?? [];
      organizations.value = data.organizations ?? [];
      departments.value = data.departments ?? [];
      security_levels.value = data.security_levels ?? [];
      loaded.value = true;
    } finally {
      loading.value = false;
    }
  }

  return {
    loading,
    loaded,
    branches,
    organizations,
    departments,
    security_levels,
    fetchCatalog,
    invalidate,
  };
});
