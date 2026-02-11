import axios, { AxiosError } from 'axios';

const API_BASE_URL = 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface PaymentIntent {
  intent_type: 'PAYMENT' | 'BALANCE_INQUIRY' | 'TRANSACTION_HISTORY' | 'SPENDING_ANALYSIS';
  amount?: number | null;
  currency: string;
  merchant_vpa?: string | null;
  confidence_score: number;
  raw_input: string;
}

export interface CommandResponse {
  status: string;
  message: string;
  intent?: PaymentIntent;
  policy_decision?: string;
  execution_result?: any;
  risk_info?: {
    score: number;
    violations: string[];
    passed_rules?: string[];
    reason?: string;
  };
  context_used?: Record<string, any> | null;
  user_state?: {
    balance: number;
    daily_spend: number;
    daily_limit: number;
    trust_score: number;
    recent_transactions: Array<{ merchant: string; amount: number; status: string; timestamp: string }>;
  } | null;
  fraud_intel?: {
    merchant_vpa: string;
    badge: string;
    badge_emoji: string;
    community_score: number;
    scam_rate: number;
    total_reports: number;
    scam_reports: number;
    risk_state: string;
  } | null;
}

export const processCommand = async (text: string, userId: string = 'user_default'): Promise<CommandResponse> => {
  try {
    const response = await apiClient.post<CommandResponse>('/process-command', {
      text,
      user_id: userId,
    });
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      const axiosError = error as AxiosError<any>; // Use precise type if possible
      // Return a structured error response that the UI can handle
      return {
        status: 'error',
        message: axiosError.response?.data?.detail || axiosError.message || 'Network Error',
        policy_decision: 'ERROR'
      };
    }
    throw error;
  }
};


// ── Fraud Intelligence Types ──────────────────────────────────────────
export interface MerchantScoreData {
  merchant_vpa: string;
  community_score: number;
  scam_rate: number;
  badge: string;
  badge_emoji: string;
  risk_state: string;
  total_reports: number;
  scam_reports: number;
  legitimate_reports: number;
  last_updated: string | null;
}

export interface MerchantDetailResponse {
  score: MerchantScoreData & { suspicious_reports: number };
  reports: Array<{
    report_id: string;
    report_type: string;
    reason: string | null;
    reporter_id: string;
    timestamp: string | null;
    verified: boolean;
  }>;
}

export interface FraudStats {
  total_reports: number;
  total_merchants: number;
  flagged_merchants: number;
  safe_merchants: number;
  scam_reports: number;
}

export interface ReportResponse {
  status: string;
  report_id: string;
  updated_badge: string;
  updated_badge_emoji: string;
  updated_score: number;
}

// ── Fraud Intelligence API Functions ──────────────────────────────────
export const getScamMerchants = async (limit: number = 20): Promise<MerchantScoreData[]> => {
  const response = await apiClient.get<MerchantScoreData[]>('/fraud/scammers', { params: { limit } });
  return response.data;
};

export const getMerchantDetail = async (vpa: string): Promise<MerchantDetailResponse> => {
  const response = await apiClient.get<MerchantDetailResponse>(`/fraud/merchant/${encodeURIComponent(vpa)}`);
  return response.data;
};

export const reportMerchant = async (
  merchantVpa: string,
  reportType: 'SCAM' | 'SUSPICIOUS' | 'LEGITIMATE',
  reason?: string,
  userId: string = 'user_default',
): Promise<ReportResponse> => {
  const response = await apiClient.post<ReportResponse>('/fraud/report', {
    merchant_vpa: merchantVpa,
    report_type: reportType,
    reason: reason || null,
    user_id: userId,
  });
  return response.data;
};

export const getFraudStats = async (): Promise<FraudStats> => {
  const response = await apiClient.get<FraudStats>('/fraud/stats');
  return response.data;
};

export interface UserState {
  balance: number;
  daily_spend: number;
  daily_limit: number;
  trust_score: number;
  recent_transactions: Array<{
    merchant: string;
    amount: number;
    status: string;
    timestamp: string;
  }>;
}

export const getUserState = async (userId: string = 'user_default'): Promise<UserState> => {
  const response = await apiClient.get<UserState>(`/user-state/${userId}`);
  return response.data;
};

export const executeApproved = async (
  merchantVpa: string,
  amount: number,
  rawInput: string = '',
  userId: string = 'user_default',
): Promise<CommandResponse> => {
  const response = await apiClient.post<CommandResponse>('/execute-approved', {
    user_id: userId,
    merchant_vpa: merchantVpa,
    amount,
    raw_input: rawInput,
  });
  return response.data;
};
