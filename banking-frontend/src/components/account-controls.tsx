"use client";
import { useState } from "react";
import { api, download, type Card } from "@/lib/api";

export function CardControls({
  card,
  updated,
}: {
  card: Card;
  updated: () => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function change(path: string, body: unknown) {
    setBusy(true);
    setError("");
    try {
      await api(`/cards/${card.id}/${path}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
      await updated();
      setEditing(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  if (card.card_status === "cancelled") return null;
  return (
    <div className="card-controls">
      <p>
        Daily limit: {card.daily_limit || "Not set"} · Monthly limit:{" "}
        {card.monthly_limit || "Not set"}
      </p>
      <div className="ops-toolbar">
        <button className="secondary" onClick={() => setEditing(!editing)}>
          Edit card limits
        </button>
        <button
          className="secondary"
          disabled={busy}
          onClick={() => {
            if (
              window.confirm(
                "Permanently cancel this sandbox card? This cannot be undone.",
              )
            )
              void change("status", { status: "cancelled" });
          }}
        >
          Cancel card
        </button>
      </div>
      {editing && (
        <form
          className="ops-form"
          onSubmit={(e) => {
            e.preventDefault();
            const values = new FormData(e.currentTarget);
            void change("limits", {
              daily_limit: values.get("daily") || null,
              monthly_limit: values.get("monthly") || null,
            });
          }}
        >
          <label>
            Daily limit
            <input
              name="daily"
              type="number"
              min="0.01"
              step="0.01"
              defaultValue={card.daily_limit || ""}
              placeholder="No limit"
            />
          </label>
          <label>
            Monthly limit
            <input
              name="monthly"
              type="number"
              min="0.01"
              step="0.01"
              defaultValue={card.monthly_limit || ""}
              placeholder="No limit"
            />
          </label>
          <button className="primary" disabled={busy}>
            Save limits
          </button>
        </form>
      )}
      {error && (
        <p role="alert" className="ops-error">
          {error}
        </p>
      )}
    </div>
  );
}

export function StatementDownload({ accountId }: { accountId: string }) {
  const today = new Date().toISOString().slice(0, 10);
  const [start, setStart] = useState(`${today.slice(0, 8)}01`);
  const [end, setEnd] = useState(today);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <form
      className="statement-form"
      onSubmit={async (e) => {
        e.preventDefault();
        setError("");
        setBusy(true);
        try {
          await download(
            `/ledger/${accountId}/statement-csv?${new URLSearchParams({ start: `${start}T00:00:00Z`, end: `${end}T23:59:59.999999Z` })}`,
            `statement-${accountId}-${start}-${end}.csv`,
          );
        } catch (e) {
          setError((e as Error).message);
        } finally {
          setBusy(false);
        }
      }}
    >
      <label>
        From (UTC)
        <input
          type="date"
          required
          value={start}
          max={end}
          onChange={(e) => setStart(e.target.value)}
        />
      </label>
      <label>
        Through (UTC)
        <input
          type="date"
          required
          value={end}
          min={start}
          max={today}
          onChange={(e) => setEnd(e.target.value)}
        />
      </label>
      <button className="secondary" disabled={busy}>
        Download CSV
      </button>
      {error && (
        <p role="alert" className="ops-error">
          {error}
        </p>
      )}
    </form>
  );
}
