import { computed } from "vue";
import { useAclCatalogStore } from "@/stores/aclCatalog";

const DEFAULT_SECURITY_OPTIONS = [
  { value: 1, label: "1 · 公开" },
  { value: 2, label: "2 · 内部" },
  { value: 3, label: "3 · 敏感" },
  { value: 4, label: "4 · 机密" },
];

/** 将字典表转为 el-select 选项；与 `useAclCatalogStore` 配合使用 */
export function useAclCatalogOptions() {
  const store = useAclCatalogStore();

  const branchSelectOptions = computed(() =>
    store.branches.map((b) => ({
      value: b.code,
      label: `${b.name}（${b.code}）`,
    })),
  );

  const orgSelectOptions = computed(() =>
    store.organizations.map((o) => ({
      value: o.org_code,
      label: `${o.name}（${o.org_code}）`,
    })),
  );

  const deptSelectOptions = computed(() =>
    store.departments.map((d) => ({
      value: d.code,
      label: d.org_code
        ? `${d.name}（${d.code}）· ${d.org_code}`
        : `${d.name}（${d.code}）`,
    })),
  );

  const securitySelectOptions = computed(() => {
    if (store.security_levels.length) {
      return store.security_levels.map((s) => ({
        value: s.level,
        label: `${s.level} · ${s.label}`,
      }));
    }
    return DEFAULT_SECURITY_OPTIONS;
  });

  /** 密级数值 → 展示名（表格列等） */
  const securityLabelMap = computed(() => {
    const m: Record<number, string> = {
      1: "公开",
      2: "内部",
      3: "敏感",
      4: "机密",
    };
    for (const s of store.security_levels) {
      m[s.level] = s.label;
    }
    return m;
  });

  return {
    store,
    branchSelectOptions,
    orgSelectOptions,
    deptSelectOptions,
    securitySelectOptions,
    securityLabelMap,
    fetchAcl: (force?: boolean) => store.fetchCatalog(force),
  };
}
