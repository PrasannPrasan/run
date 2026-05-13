export type AuthUser = {
  id: number;
  email: string;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
  user: AuthUser;
};

export type LookupField = {
  value: unknown;
  confidence: number;
  sources: Array<{ provider: string; providerRef?: string | null; note?: string | null }>;
};

export type LookupResult = {
  id: number;
  status: string;
  linkedinUrl: string;
  fields: Record<string, LookupField>;
  workHistory: Array<{
    company?: string | null;
    title?: string | null;
    startDate?: string | null;
    endDate?: string | null;
    isCurrent: boolean;
    confidence: number;
    provider: string;
  }>;
  costs: Array<{
    provider: string;
    costUsd?: number | null;
    costUnits?: number | null;
    unitName?: string | null;
    isEstimated: boolean;
    note?: string | null;
  }>;
  providerCalls?: Array<{
    provider: string;
    stage: string;
    success: boolean;
    errorMessage?: string | null;
    providerRef?: string | null;
  }>;
};

export type ProviderStrategy = {
  recommendedOrder: string[];
  providers: Array<{
    name: string;
    stage: string;
    enabled: boolean;
    bestFor: string;
    costModel: string;
    sourceUrl: string;
  }>;
  logic: string[];
  freeTierPlan: string[];
  complianceNote: string;
};

export type AdminProviderStatus = {
  provider: string;
  enabled: boolean;
  successes: number;
  failures: number;
  latestError?: string | null;
};

export type AdminUser = {
  id: number;
  email: string;
  createdAt?: string | null;
  lookupCount: number;
};

export type AdminLookup = {
  id: number;
  userEmail?: string | null;
  linkedinUrl: string;
  status: string;
  errorMessage?: string | null;
  createdAt?: string | null;
  updatedAt?: string | null;
  totalCostUsd: number;
  costs: LookupResult["costs"];
  providerCalls: NonNullable<LookupResult["providerCalls"]>;
};

export type AdminOverview = {
  admin: AuthUser;
  users: AdminUser[];
  lookups: AdminLookup[];
  providerStatus: AdminProviderStatus[];
};
