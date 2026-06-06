export type TokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
};

export type UserResponse = {
  id: number;
  email: string;
  is_active: boolean;
  is_verified: boolean;
  default_provider_id: number | null;
};

export type AuthResponse = {
  user: UserResponse;
  tokens: TokenResponse;
};

export type ProviderConfig = {
  id: number;
  name: string;
  provider: string;
  model: string;
  is_default: boolean;
  capability_flags: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type ProviderCreateInput = {
  name: string;
  provider: string;
  model: string;
  api_key: string;
  is_default?: boolean;
};

export type ProviderUpdateInput = Partial<ProviderCreateInput>;

export type ProviderKeyRevealInput = {
  password: string;
};

export type ProviderTestResponse = {
  ok: boolean;
  provider_config_id: number;
  capability_flags: Record<string, unknown>;
  error: string | null;
};

export type TaskState =
  | "PERMISSION_GRANTED"
  | "SCRAPING"
  | "SCRAPED"
  | "LLM_PROCESSING"
  | "COMPLETED"
  | "FAILED"
  | string;

export type TaskResponse = {
  task_id: number;
  state: TaskState;
  url: string;
  error: string | null;
  result: Record<string, unknown> | null;
  message: string | null;
  created_at: string | null;
  content_length: number | null;
};

export type ProviderKeyResponse = {
  api_key: string;
};

export type HealthResponse = Record<string, unknown>;
