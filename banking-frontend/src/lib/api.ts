let access = "";
let refresh = "";
let refreshing: Promise<boolean> | null = null;
export function setTokens(tokens: {
  access_token: string;
  refresh_token: string;
}) {
  access = tokens.access_token;
  refresh = tokens.refresh_token;
}
export async function logout() {
  try {
    if (refresh)
      await api("/auth/logout", {
        method: "POST",
        body: JSON.stringify({ refresh_token: refresh }),
      });
  } finally {
    access = "";
    refresh = "";
  }
}
async function renew() {
  const response = await fetch("/api/auth/refresh", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
  });
  if (!response.ok) return false;
  setTokens(await response.json());
  return true;
}
export async function api<T = unknown>(
  path: string,
  options: RequestInit = {},
  retry = true,
): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...options,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(access ? { Authorization: `Bearer ${access}` } : {}),
      ...options.headers,
    },
  });
  if (
    response.status === 401 &&
    refresh &&
    retry &&
    !path.startsWith("/auth/")
  ) {
    refreshing ||= renew().finally(() => {
      refreshing = null;
    });
    if (await refreshing) return api<T>(path, options, false);
  }
  if (response.status === 204) return undefined as T;
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      Array.isArray(data.detail)
        ? data.detail.map((x: { msg: string }) => x.msg).join(". ")
        : data.detail || "Request could not be completed",
    );
  return data;
}
export const post = <T = unknown>(path: string, body: unknown) =>
  api<T>(path, { method: "POST", body: JSON.stringify(body) });
export type Account = {
  id: string;
  account_name: string;
  account_number: string;
  currency_code: string;
  account_type: string;
  account_status: string;
  balance?: string;
};
export type Person = {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  kyc_status?: string;
  role?: string;
  customer_status?: string;
};
export type Transaction = {
  id: string;
  from_account_id: string;
  to_account_id: string | null;
  amount: string;
  fee_amount: string;
  currency_code: string;
  status: string;
  transaction_type: string;
  reference_number: string;
  transaction_date: string;
};
export type Card = {
  id: string;
  account_id: string;
  card_last_4: string;
  card_holder_name: string;
  expiry_month: number;
  expiry_year: number;
  card_status: string;
};
