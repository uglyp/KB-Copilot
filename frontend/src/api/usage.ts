import { http } from "@/api/http";

export interface EndpointBucket {
  turns: number;
  embed_prompt_tokens: number;
  embed_total_tokens: number;
  chat_prompt_tokens: number;
  chat_completion_tokens: number;
  chat_total_tokens: number;
}

export interface ModelBucket {
  chat_model_id: number | null;
  display_name: string | null;
  turns: number;
  chat_prompt_tokens: number;
  chat_completion_tokens: number;
  chat_total_tokens: number;
  embed_prompt_tokens: number;
  embed_total_tokens: number;
}

export interface UsageSummary {
  range_days: number;
  since: string;
  totals: EndpointBucket;
  by_endpoint: Record<string, EndpointBucket>;
  by_model: ModelBucket[];
}

export interface UsageRecordRow {
  id: number;
  created_at: string;
  conversation_id: number;
  conversation_title: string | null;
  endpoint_kind: string;
  chat_model_id: number | null;
  model_display_name: string | null;
  embed_prompt_tokens: number | null;
  embed_total_tokens: number | null;
  chat_prompt_tokens: number | null;
  chat_completion_tokens: number | null;
  chat_total_tokens: number | null;
  embed_is_estimated: boolean;
  chat_is_estimated: boolean;
}

export interface UsageRecordsPage {
  total: number;
  items: UsageRecordRow[];
}

export function fetchUsageSummary(days: number) {
  return http.get<UsageSummary>("/usage/summary", { params: { days } });
}

export function fetchUsageRecords(params: {
  skip?: number;
  limit?: number;
  conversation_id?: number;
  days?: number;
}) {
  return http.get<UsageRecordsPage>("/usage/records", { params });
}
