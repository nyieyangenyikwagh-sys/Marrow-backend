"use client";
import { useEffect, useState, type FormEvent } from "react";
import { api, post, download } from "@/lib/api";

type Row = {
  id: string;
  first_name?: string;
  last_name?: string;
  email?: string;
  customer_id?: string;
  customer_status?: string;
  kyc_status?: string;
  risk_score?: number;
  risk_level?: string;
  resolution?: string;
  flags_triggered?: string[];
  transaction_id?: string;
  resolution_notes?: string;
  checked_at?: string;
  account_name?: string;
  account_number?: string;
  account_status?: string;
  currency_code?: string;
  daily_limit?: string | null;
  monthly_limit?: string | null;
  transaction_limit?: string | null;
  action?: string;
  entity_type?: string;
  entity_id?: string;
  actor_id?: string;
  actor_type?: string;
  created_at?: string;
  old_values?: unknown;
  new_values?: unknown;
  document_type?: string;
  status?: string;
  amount?: string;
  reference_number?: string;
};
const endpoints: Record<string, string> = {
  Customers: "customers",
  Accounts: "accounts",
  "AML checks": "aml",
  "Audit log": "audit",
  Reviews: "kyc",
  "Transfer reviews": "transactions",
};

export function Operations({
  section,
  role,
}: {
  section: string;
  role?: string;
}) {
  const [rows, setRows] = useState<Row[]>([]);
  const [page, setPage] = useState(0);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("");
  const [notes, setNotes] = useState("");
  const [revision, setRevision] = useState(0);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [selected, setSelected] = useState<Row | null>(null);
  const [documents, setDocuments] = useState<Record<
    string,
    string | null
  > | null>(null);
  const [queue, setQueue] = useState("Reviews");
  const active = section === "Reviews" ? queue : section;
  const canEdit = role !== "support";
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    setSelected(null);
    setDocuments(null);
    const params = new URLSearchParams({
      limit: "25",
      offset: String(page * 25),
      q: query,
    });
    if (active === "AML checks" && filter) params.set("resolution", filter);
    if (active === "Transfer reviews")
      params.set("status", filter || "pending");
    api<Row[]>(`/admin/${endpoints[active]}?${params}`, {
      signal: controller.signal,
    })
      .then(setRows)
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [active, page, query, filter, revision]);
  async function run(task: () => Promise<unknown>, message = "Change saved.") {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await task();
      setNotice(message);
      setRevision((n) => n + 1);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function reason() {
    if (notes.trim().length < 3)
      throw new Error("Enter a decision reason of at least three characters.");
    return notes.trim();
  }
  async function view(row: Row) {
    setError("");
    setBusy(true);
    setDocuments(null);
    setSelected(null);
    try {
      const result = await api<Record<string, string | null>>(
        `/admin/kyc/${row.id}`,
      );
      setSelected(row);
      setDocuments(result);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function edit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    if (!selected) return;
    void run(async () => {
      if (active === "Customers")
        return api(`/admin/customers/${selected.id}/risk`, {
          method: "PATCH",
          body: JSON.stringify({
            score: Number(values.score),
            reason: reason(),
          }),
        });
      return api(`/accounts/${selected.id}/limits`, {
        method: "PATCH",
        body: JSON.stringify({
          daily_limit: values.daily_limit || null,
          monthly_limit: values.monthly_limit || null,
          transaction_limit: values.transaction_limit || null,
        }),
      });
    });
  }
  return (
    <section className="operations panel">
      <div className="section-heading">
        <div>
          <h2>{section === "Reviews" ? "Review workbench" : section}</h2>
          <p>
            Search records, inspect details, and keep a clear record of each
            decision.
          </p>
        </div>
        <button
          className="secondary"
          disabled={loading || busy}
          onClick={() => setRevision((n) => n + 1)}
        >
          Refresh
        </button>
      </div>
      {section === "Reviews" && (
        <div className="ops-toolbar">
          {["Reviews", "Transfer reviews"].map((name) => (
            <button
              className={queue === name ? "primary" : "secondary"}
              key={name}
              onClick={() => {
                setQueue(name);
                setPage(0);
                setFilter("");
              }}
            >
              {name === "Reviews" ? "Identity documents" : name}
            </button>
          ))}
        </div>
      )}
      <div className="ops-toolbar">
        {["Customers", "Accounts", "Audit log"].includes(active) && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setQuery(
                String(new FormData(e.currentTarget).get("search") || ""),
              );
              setPage(0);
            }}
          >
            <label>
              Search {active.toLowerCase()}
              <input
                name="search"
                placeholder={
                  active === "Audit log"
                    ? "Action, entity or actor ID"
                    : "Name, number or ID"
                }
                maxLength={100}
              />
            </label>
            <button className="secondary">Search</button>
          </form>
        )}
        {active === "AML checks" && (
          <label>
            Resolution
            <select
              value={filter}
              onChange={(e) => {
                setFilter(e.target.value);
                setPage(0);
              }}
            >
              <option value="">All resolutions</option>
              {["review", "blocked", "approved", "pending"].map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </label>
        )}
        {active === "Transfer reviews" && (
          <label>
            Transfer status
            <select
              value={filter || "pending"}
              onChange={(e) => {
                setFilter(e.target.value);
                setPage(0);
              }}
            >
              <option value="pending">Pending decisions</option>
              <option value="completed">
                Completed — eligible for reversal
              </option>
            </select>
          </label>
        )}
      </div>
      {canEdit && active !== "Audit log" && (
        <label className="ops-reason">
          Decision reason
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            maxLength={500}
            placeholder="Record the reason for status changes, risk assessments and reviews."
          />
        </label>
      )}
      {error && (
        <p role="alert" className="ops-error">
          {error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      {loading ? (
        <p role="status">Loading records…</p>
      ) : rows.length === 0 ? (
        <p>No records on this page.</p>
      ) : (
        <div className="ops-records">
          {rows.map((row) => (
            <article className="ops-record" key={row.id}>
              <div className="ops-record-main">
                <strong>
                  {row.email ||
                    row.account_name ||
                    row.reference_number ||
                    row.action?.replaceAll("_", " ") ||
                    row.document_type?.replaceAll("_", " ") ||
                    `${row.risk_level} risk · score ${row.risk_score}`}
                </strong>
                <small>{row.id}</small>
                <span>
                  {row.customer_status ||
                    row.account_status ||
                    row.status ||
                    row.resolution ||
                    row.entity_type ||
                    "Awaiting identity review"}
                </span>
                {row.customer_id && <small>Customer: {row.customer_id}</small>}
                {row.account_number && (
                  <small>
                    {row.account_number} · {row.currency_code}
                  </small>
                )}
                {row.amount && (
                  <span>
                    {row.currency_code} {row.amount}
                  </span>
                )}
                {row.flags_triggered && (
                  <small>{row.flags_triggered.join(", ")}</small>
                )}
                {row.resolution_notes && <p>{row.resolution_notes}</p>}
                {(row.created_at || row.checked_at) && (
                  <small>
                    {new Date(
                      (row.created_at || row.checked_at)!,
                    ).toLocaleString()}
                  </small>
                )}
              </div>
              <div className="ops-actions">
                {active === "Customers" && (
                  <>
                    <span>
                      KYC: {row.kyc_status} · Risk: {row.risk_score} (
                      {row.risk_level})
                    </span>
                    {canEdit && (
                      <>
                        <button
                          className="secondary"
                          disabled={busy}
                          onClick={() => setSelected(row)}
                        >
                          Assess risk
                        </button>
                        {row.customer_status !== "closed" && (
                          <button
                            className="secondary"
                            disabled={busy}
                            onClick={() =>
                              run(() =>
                                post(
                                  `/customers/${row.id}/${row.customer_status === "active" ? "freeze" : "unfreeze"}?reason=${encodeURIComponent(reason())}`,
                                  {},
                                ),
                              )
                            }
                          >
                            {row.customer_status === "active"
                              ? "Freeze customer"
                              : "Unfreeze customer"}
                          </button>
                        )}
                      </>
                    )}
                  </>
                )}
                {active === "Accounts" && row.account_status !== "closed" && (
                  <>
                    <button
                      className="secondary"
                      disabled={busy}
                      onClick={() => setSelected(row)}
                    >
                      Edit limits
                    </button>
                    <button
                      className="secondary"
                      disabled={busy}
                      onClick={() =>
                        run(() =>
                          post(
                            `/accounts/${row.id}/${row.account_status === "active" ? "freeze" : "unfreeze"}`,
                            { reason: reason() },
                          ),
                        )
                      }
                    >
                      {row.account_status === "active" ? "Freeze" : "Unfreeze"}
                    </button>
                    <button
                      className="secondary"
                      disabled={busy}
                      onClick={() => {
                        if (
                          window.confirm(
                            "Permanently close this account? It must have zero balance and no pending transfers.",
                          )
                        )
                          void run(() =>
                            post(`/accounts/${row.id}/close`, {
                              reason: reason(),
                            }),
                          );
                      }}
                    >
                      Close account
                    </button>
                  </>
                )}
                {active === "Reviews" && (
                  <button
                    className="secondary"
                    disabled={busy}
                    onClick={() => view(row)}
                  >
                    Inspect documents
                  </button>
                )}
                {(active === "Transfer reviews" ||
                  (active === "AML checks" &&
                    row.transaction_id &&
                    ["review", "pending"].includes(row.resolution || ""))) &&
                  (row.status === "completed" ? (
                    <button
                      className="secondary"
                      disabled={busy}
                      onClick={() => {
                        if (
                          window.confirm(
                            "Reverse this transfer, including its fees?",
                          )
                        )
                          void run(() =>
                            post(`/transactions/${row.id}/reverse`, {
                              reason: reason(),
                            }),
                          );
                      }}
                    >
                      Reverse transfer
                    </button>
                  ) : (
                    ["approve", "reject"].map((decision) => (
                      <button
                        key={decision}
                        className="secondary"
                        disabled={busy}
                        onClick={() =>
                          run(() =>
                            post(
                              `/transactions/${row.transaction_id || row.id}/review/${decision}`,
                              { notes: reason() },
                            ),
                          )
                        }
                      >
                        {decision === "approve"
                          ? "Approve transfer"
                          : "Reject transfer"}
                      </button>
                    ))
                  ))}
                {active === "Audit log" && (
                  <details>
                    <summary>Event details</summary>
                    <p>
                      Actor: {row.actor_type} · {row.actor_id || "system"}
                    </p>
                    <p>Entity: {row.entity_id}</p>
                    <pre>
                      {JSON.stringify(
                        { before: row.old_values, after: row.new_values },
                        null,
                        2,
                      )}
                    </pre>
                  </details>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
      <div className="ops-toolbar">
        <button
          className="secondary"
          disabled={page === 0 || loading || busy}
          onClick={() => setPage((p) => p - 1)}
        >
          Previous
        </button>
        <span>Page {page + 1}</span>
        <button
          className="secondary"
          disabled={rows.length < 25 || loading || busy}
          onClick={() => setPage((p) => p + 1)}
        >
          Next
        </button>
      </div>
      {selected && (
        <div className="ops-editor">
          <button
            className="text-button"
            onClick={() => {
              setSelected(null);
              setDocuments(null);
            }}
          >
            Close details
          </button>
          <h3>
            {selected.email || selected.account_name || "Identity document"}
          </h3>
          {documents ? (
            <>
              <div>
                {Object.entries(documents).map(([key, value]) => (
                  <p key={key}>
                    <strong>{key.replaceAll("_", " ")}: </strong>
                    {value?.startsWith("attachment:") ? (
                      <button
                        className="secondary"
                        disabled={busy}
                        onClick={async () => {
                          try {
                            await download(
                              `/admin/attachments/${value.split(":")[1]}`,
                            );
                          } catch (e) {
                            setError((e as Error).message);
                          }
                        }}
                      >
                        Download for review
                      </button>
                    ) : (
                      value || "Not provided"
                    )}
                  </p>
                ))}
              </div>
              <div className="ops-toolbar">
                {[true, false].map((approve) => (
                  <button
                    className="secondary"
                    disabled={busy}
                    key={String(approve)}
                    onClick={() =>
                      run(() =>
                        post(`/kyc/${selected.id}/review`, {
                          approve,
                          notes: reason(),
                        }),
                      )
                    }
                  >
                    {approve ? "Approve identity" : "Reject identity"}
                  </button>
                ))}
              </div>
            </>
          ) : (
            <form onSubmit={edit} className="ops-form" key={selected.id}>
              {active === "Customers" ? (
                <>
                  <label>
                    Risk score (0–100)
                    <input
                      name="score"
                      type="number"
                      min="0"
                      max="100"
                      step="1"
                      required
                      defaultValue={selected.risk_score}
                    />
                  </label>
                  <p>
                    Applies to future transfer decisions. Existing failed
                    transfers stay failed.
                  </p>
                </>
              ) : (
                ["daily_limit", "monthly_limit", "transaction_limit"].map(
                  (field) => (
                    <label key={field}>
                      {field.replaceAll("_", " ")}
                      <input
                        type="number"
                        name={field}
                        step="0.01"
                        min="0.01"
                        defaultValue={
                          (selected[field as keyof Row] as string) || ""
                        }
                        placeholder="No limit"
                      />
                    </label>
                  ),
                )
              )}
              <button className="primary" disabled={busy}>
                Save changes
              </button>
            </form>
          )}
        </div>
      )}
    </section>
  );
}
