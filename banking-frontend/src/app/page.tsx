"use client";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";
import {
  ArrowDownLeft,
  ArrowUpRight,
  ArrowRight,
  Plus,
  Wallet,
  LayoutDashboard,
  ArrowLeftRight,
  CreditCard,
  ShieldCheck,
  Settings,
  LogOut,
  ChevronDown,
  X,
  Check,
  Copy,
  Menu,
  Search,
  RefreshCw,
  FileText,
  Users,
  Clock,
  Landmark,
  Eye,
  EyeOff,
} from "lucide-react";
import {
  api,
  post,
  setTokens,
  logout,
  type Account,
  type Person,
  type Transaction,
  type Card,
} from "@/lib/api";

import { Operations } from "@/components/operations";
import { CardControls, StatementDownload } from "@/components/account-controls";

const money = (v: string | number, currency = "CAD") =>
  new Intl.NumberFormat("en-CA", { style: "currency", currency }).format(
    Number(v),
  );
const date = (v: string) =>
  new Date(v).toLocaleDateString("en-CA", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
type Modal =
  "transfer" | "account" | "card" | "kyc" | "profile" | "help" | null;
function Badge({ value }: { value: string }) {
  return (
    <span
      className={`badge ${["active", "verified", "completed", "approved"].includes(value) ? "good" : ["pending", "frozen", "review"].includes(value) ? "warn" : "muted"}`}
    >
      <i />
      {value.replaceAll("_", " ")}
    </span>
  );
}

export default function Home() {
  const [person, setPerson] = useState<Person | null>(null);
  const [staff, setStaff] = useState(false);
  const [tab, setTab] = useState("Overview");
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [cards, setCards] = useState<Card[]>([]);
  const [summary, setSummary] = useState<Record<string, number>>({});
  const [modal, setModal] = useState<Modal>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [mobile, setMobile] = useState(false);
  const [hidden, setHidden] = useState(false);
  const [selectedCurrency, setSelectedCurrency] = useState("CAD");
  const [historyPage, setHistoryPage] = useState(0);
  const dialogRef = useRef<HTMLElement>(null);
  const transferKey = useRef("");
  const transferPayload = useRef("");

  const load = useCallback(async (isStaff: boolean, page = 0) => {
    setLoading(true);
    try {
      if (isStaff) {
        const user = await api<Person>("/admin/me");
        const stats = await api<Record<string, number>>("/admin/summary");
        setSummary(stats);
        if (user.role !== "support") {
          const tx = await api<Transaction[]>(
            `/admin/transactions?limit=50&offset=${page * 50}`,
          );
          setTransactions(tx);
        }
        setPerson(user);
      } else {
        const [user, acc, tx, cardList] = await Promise.all([
          api<Person>("/customers/me"),
          api<Account[]>("/accounts/me"),
          api<Transaction[]>(`/transactions?limit=50&offset=${page * 50}`),
          api<Card[]>("/cards"),
        ]);
        setTransactions(tx);
        setCards(cardList);
        setAccounts(
          await Promise.all(
            acc.map(async (a) => ({
              ...a,
              ...(await api<{ balance: string }>(`/ledger/${a.id}/balance`)),
            })),
          ),
        );
        setPerson(user);
      }
    } finally {
      setLoading(false);
    }
  }, []);
  async function refresh() {
    setError("");
    try {
      await load(staff, historyPage);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function action(fn: () => Promise<unknown>, success: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await fn();
      setNotice(typeof result === "string" ? result : success);
      await load(staff, historyPage);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function open(value: Modal) {
    setError("");
    setModal(value);
    if (value === "transfer") {
      transferKey.current = crypto.randomUUID();
      transferPayload.current = "";
    }
  }
  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(""), 6000);
    return () => clearTimeout(timer);
  }, [notice]);
  useEffect(() => {
    if (!modal) return;
    const previous = document.activeElement as HTMLElement | null;
    const dialog = dialogRef.current;
    const selectors =
      "button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled)";
    dialog?.querySelector<HTMLElement>(selectors)?.focus();
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busy) setModal(null);
      if (event.key === "Tab") {
        const items = Array.from(
          dialog?.querySelectorAll<HTMLElement>(selectors) || [],
        );
        const first = items[0],
          last = items[items.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }
    };
    window.addEventListener("keydown", handler);
    return () => {
      window.removeEventListener("keydown", handler);
      previous?.focus();
    };
  }, [modal, busy]);
  if (!person)
    return (
      <Login
        onLogin={async (isStaff) => {
          setStaff(isStaff);
          setTab("Overview");
          setHistoryPage(0);
          await load(isStaff);
        }}
      />
    );
  const nav = staff
    ? ([
        ["Overview", LayoutDashboard],
        ["Reviews", ShieldCheck],
        ["Customers", Users],
        ["Accounts", Wallet],
        ["AML checks", ShieldCheck],
        ["Activity", ArrowLeftRight],
        ["Audit log", FileText],
      ] as const)
    : ([
        ["Overview", LayoutDashboard],
        ["Accounts", Wallet],
        ["Transfers", ArrowLeftRight],
        ["Activity", Clock],
        ["Cards", CreditCard],
        ["Identity", ShieldCheck],
      ] as const);
  const currencyAccounts = accounts.filter(
    (a) => a.currency_code === selectedCurrency,
  );
  const total = currencyAccounts.reduce(
    (sum, a) => sum + Number(a.balance || 0),
    0,
  );
  const matches = transactions.filter((t) =>
    `${t.reference_number} ${t.status} ${t.amount} ${t.transaction_type}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  const ownedIds = new Set(accounts.map((a) => a.id));
  const pendingCount =
    (summary.pending_transfers || 0) + (summary.pending_kyc || 0);
  const title = tab === "Overview" ? `Welcome back, ${person.first_name}` : tab;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const data = Object.fromEntries(form.entries());
    await action(
      async () => {
        if (modal === "account")
          await post("/accounts", {
            ...data,
            account_type: data.account_type || "checking",
          });
        if (modal === "card") await post("/cards", data);
        if (modal === "kyc") {
          const references: Record<string, string> = {};
          for (const [field, role] of [
            ["document_front_url", "front"],
            ["document_back_url", "back"],
            ["selfie_url", "selfie"],
          ]) {
            const file = form.get(field) as File;
            if (!file?.size) continue;
            if (file.size > 5 * 1024 * 1024)
              throw new Error("Each identity file must be 5 MB or smaller.");
            const upload = new FormData();
            upload.set("file", file);
            upload.set("role", role);
            const result = await api<{ reference: string }>(
              "/kyc/attachments",
              { method: "POST", body: upload },
            );
            references[field] = result.reference;
          }
          await post("/kyc/documents", {
            document_type: data.document_type,
            document_number: data.document_number,
            ...references,
            expiry_date: data.expiry_date || null,
          });
        }
        if (modal === "profile")
          await api("/customers/me", {
            method: "PATCH",
            body: JSON.stringify(data),
          });
        if (modal === "transfer") {
          const payload = JSON.stringify(data);
          if (transferPayload.current && transferPayload.current !== payload)
            transferKey.current = crypto.randomUUID();
          transferPayload.current = payload;
          const result = await post<Transaction>("/transactions/transfer", {
            ...data,
            idempotency_key: transferKey.current,
          });
          if (result.status === "failed")
            throw new Error(
              "This transfer was declined by compliance. No money moved.",
            );
          setModal(null);
          return result.status === "pending"
            ? "Transfer submitted for review. No money has moved yet."
            : "Transfer completed.";
        }
        setModal(null);
      },
      modal === "transfer"
        ? "Transfer request processed."
        : "Saved successfully.",
    );
  }

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobile ? "is-open" : ""}`}>
        <a className="brand" href="/" aria-label="Morrow home">
          MORROW<span>®</span>
        </a>
        <div className="workspace">
          <span className="workspace-icon">
            <Landmark size={18} />
          </span>
          <div>
            <strong>{staff ? "Banking operations" : "Personal banking"}</strong>
            <small>
              {staff ? "Staff workspace" : "Your everyday, upgraded"}
            </small>
          </div>
          <ChevronDown size={15} />
        </div>
        <div className="nav-label">YOUR WORKSPACE</div>
        <nav>
          {nav
            .filter(
              ([name]) =>
                person.role !== "support" ||
                ["Overview", "Customers"].includes(name),
            )
            .map(([name, Icon]) => (
              <button
                key={name}
                className={tab === name ? "active" : ""}
                onClick={() => {
                  setTab(name);
                  setSearch("");
                  setMobile(false);
                }}
              >
                <Icon size={19} />
                {name}
                {name === "Reviews" && pendingCount > 0 && (
                  <span className="nav-count">{pendingCount}</span>
                )}
              </button>
            ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="support-box">
            <div className="support-icon">
              <ShieldCheck size={23} />
            </div>
            <strong>A little peace of mind.</strong>
            <p>
              Every movement has a record.
              <br />
              Your money, clearly accounted for.
            </p>
            <button onClick={() => open("help")}>
              Explore your workspace <ArrowUpRight size={14} />
            </button>
          </div>
          <button
            className="settings-link"
            onClick={() => (staff ? open("help") : open("profile"))}
          >
            <Settings size={18} />{" "}
            {staff ? "Workspace information" : "Profile & settings"}
          </button>
          <button
            className="user"
            onClick={async () => {
              try {
                await logout();
              } catch {
              } finally {
                setPerson(null);
                setAccounts([]);
                setTransactions([]);
                setCards([]);
                setError("");
                setNotice("");
              }
            }}
            title="Sign out"
          >
            <span className="avatar">
              {person.first_name[0]}
              {person.last_name[0]}
            </span>
            <span>
              <strong>
                {person.first_name} {person.last_name}
              </strong>
              <small>{staff ? person.role : "Personal account"}</small>
            </span>
            <LogOut size={17} />
          </button>
        </div>
      </aside>
      {mobile && (
        <button
          className="mobile-overlay"
          aria-label="Close navigation"
          onClick={() => setMobile(false)}
        />
      )}
      <main className="main">
        <header className="topbar">
          <button
            className="icon-button mobile-menu"
            aria-label="Open navigation"
            onClick={() => setMobile(true)}
          >
            <Menu size={20} />
          </button>
          <div className="breadcrumb">
            Workspace <span>/</span> <strong>{tab}</strong>
          </div>
          <div className="topbar-right">
            <span className="sandbox">
              <i /> SANDBOX
            </span>
            <button
              className="icon-button"
              aria-label="Refresh data"
              onClick={refresh}
              disabled={loading}
            >
              <RefreshCw size={17} className={loading ? "spin" : ""} />
            </button>
            <span className="avatar small">
              {person.first_name[0]}
              {person.last_name[0]}
            </span>
          </div>
        </header>
        <div className="content">
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                {staff ? "BANKING OPERATIONS" : "A LITTLE MORE POSSIBILITY"}
              </div>
              <h1>
                {title}
                <span className="heading-dot">.</span>
              </h1>
              <p>
                {tab === "Overview"
                  ? "Your money, your moves. Here’s where things stand today."
                  : staff
                    ? "A clear view of your banking operations."
                    : "Everything you need, all in one place."}
              </p>
            </div>
            {!staff && (
              <button className="primary" onClick={() => open("transfer")}>
                <ArrowUpRight size={18} /> Move money
              </button>
            )}
          </div>
          {error && (
            <div role="alert" className="alert error">
              {error}
              <button aria-label="Dismiss error" onClick={() => setError("")}>
                <X size={16} />
              </button>
            </div>
          )}
          {notice && (
            <div role="status" className="alert success">
              <Check size={17} />
              {notice}
            </div>
          )}
          {loading && (
            <div role="status" className="loading-line">
              Updating your workspace…
            </div>
          )}

          {!staff && tab === "Overview" && (
            <>
              <div className="overview-grid">
                <section className="balance-panel">
                  <div className="panel-top">
                    <span>
                      Total available balance{" "}
                      <button
                        className="icon-button"
                        aria-label={hidden ? "Show balance" : "Hide balance"}
                        onClick={() => setHidden(!hidden)}
                      >
                        {hidden ? <EyeOff size={16} /> : <Eye size={16} />}
                      </button>
                    </span>
                    <select
                      aria-label="Balance currency"
                      value={selectedCurrency}
                      onChange={(e) => setSelectedCurrency(e.target.value)}
                    >
                      {["CAD", "USD", "GBP", "EUR"].map((c) => (
                        <option key={c}>{c}</option>
                      ))}
                    </select>
                  </div>
                  <div className="total">
                    {hidden ? "••,•••.••" : money(total, selectedCurrency)}
                    <span>{selectedCurrency}</span>
                  </div>
                  <div className="balance-caption">
                    <span className="green-dot" /> Across{" "}
                    {currencyAccounts.length} {selectedCurrency} account
                    {currencyAccounts.length === 1 ? "" : "s"}
                  </div>
                  <div className="balance-actions">
                    <button onClick={() => open("transfer")}>
                      <span>
                        <ArrowUpRight size={19} />
                      </span>
                      Send money
                    </button>
                    <button onClick={() => setTab("Accounts")}>
                      <span>
                        <ArrowDownLeft size={19} />
                      </span>
                      Account details
                    </button>
                    <button onClick={() => open("account")}>
                      <span>
                        <Plus size={19} />
                      </span>
                      Open account
                    </button>
                  </div>
                </section>
                <section className="feature-panel">
                  <span className="pill">MAKE ROOM FOR WHAT’S NEXT</span>
                  <h2>
                    Good habits.
                    <br />
                    Bigger possibilities.
                  </h2>
                  <p>
                    Give your next big thing a space of its own. Start with a
                    savings account.
                  </p>
                  <button onClick={() => open("account")}>
                    Make your next move <ArrowRight size={17} />
                  </button>
                  <div className="feature-orbit" />
                  <div className="feature-coin">
                    <span>k</span>
                  </div>
                </section>
              </div>
              <Section
                title="Your accounts"
                subtitle="A place for every part of your life."
                action={
                  <button
                    className="text-button"
                    onClick={() => setTab("Accounts")}
                  >
                    View all accounts <ArrowRight size={16} />
                  </button>
                }
              >
                <div className="account-grid">
                  {accounts.slice(0, 3).map((a) => (
                    <AccountTile
                      key={a.id}
                      account={a}
                      hidden={hidden}
                      onSelect={() => {
                        setTab("Accounts");
                      }}
                    />
                  ))}
                  {accounts.length === 0 && (
                    <Empty
                      icon={<Wallet />}
                      title="Make yourself at home"
                      text="Verify your identity, then open your first account."
                      action={
                        <button
                          className="primary"
                          onClick={() => setTab("Identity")}
                        >
                          Get started <ArrowRight size={16} />
                        </button>
                      }
                    />
                  )}
                </div>
              </Section>
            </>
          )}

          {!staff && tab === "Accounts" && (
            <Section
              title="A home for your money"
              subtitle="Balances come directly from your posted ledger entries."
              action={
                <button className="secondary" onClick={() => open("account")}>
                  <Plus size={16} /> Open account
                </button>
              }
            >
              <div className="account-grid">
                {accounts.map((a) => (
                  <div key={a.id}>
                    <AccountTile account={a} hidden={false} />
                    <div className="account-tools">
                      <button
                        onClick={() =>
                          action(async () => {
                            await navigator.clipboard.writeText(a.id);
                          }, "Account ID copied.")
                        }
                      >
                        <Copy size={14} /> Copy account ID
                      </button>
                      <button
                        onClick={() =>
                          action(async () => {
                            const start = new Date();
                            start.setUTCDate(1);
                            start.setUTCHours(0, 0, 0, 0);
                            const statement = await api(
                              `/ledger/${a.id}/statement?start=${encodeURIComponent(start.toISOString())}&end=${encodeURIComponent(new Date().toISOString())}`,
                            );
                            const url = URL.createObjectURL(
                              new Blob([JSON.stringify(statement, null, 2)], {
                                type: "application/json",
                              }),
                            );
                            const link = document.createElement("a");
                            link.href = url;
                            link.download = `statement-${a.account_number}.json`;
                            link.click();
                            URL.revokeObjectURL(url);
                          }, "Statement downloaded.")
                        }
                      >
                        <FileText size={14} /> Statement
                      </button>
                    </div>
                    <StatementDownload accountId={a.id} />
                  </div>
                ))}
              </div>
              {accounts.length === 0 && (
                <Empty
                  icon={<Wallet />}
                  title="Your first account starts here"
                  text="Complete identity verification to open a checking or savings account."
                />
              )}
            </Section>
          )}

          {!staff && tab === "Transfers" && (
            <div className="transfer-landing">
              <div className="large-icon">
                <ArrowLeftRight size={32} />
              </div>
              <h2>A little closer, in a few clicks.</h2>
              <p>
                Send money between your accounts or to another verified
                customer. Transfers stay in the same currency, with a 1% fee.
              </p>
              <button className="primary" onClick={() => open("transfer")}>
                Make a transfer <ArrowUpRight size={18} />
              </button>
              <div className="transfer-facts">
                <span>
                  <ShieldCheck size={17} /> Verified recipients
                </span>
                <span>
                  <FileText size={17} /> Every cent recorded
                </span>
                <span>
                  <Clock size={17} /> Large transfers reviewed
                </span>
              </div>
            </div>
          )}

          {((!staff && ["Overview", "Activity", "Transfers"].includes(tab)) ||
            (staff && tab === "Activity")) && (
            <Section
              title={
                tab === "Overview" ? "Recent activity" : "Transaction history"
              }
              subtitle={
                tab === "Overview"
                  ? "The little moves that make up your day."
                  : "Posted, pending, and reversed — the complete picture."
              }
              action={
                tab === "Overview" ? (
                  <button
                    className="text-button"
                    onClick={() => setTab("Activity")}
                  >
                    View all activity <ArrowRight size={16} />
                  </button>
                ) : (
                  <label className="search">
                    <Search size={16} />
                    <input
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      placeholder="Search transactions"
                    />
                  </label>
                )
              }
            >
              <TransactionTable
                rows={tab === "Overview" ? matches.slice(0, 5) : matches}
                owned={ownedIds}
                staff={staff}
              />
              {tab !== "Overview" && (
                <div className="pagination">
                  <button
                    disabled={historyPage === 0 || loading}
                    onClick={() => {
                      const page = historyPage - 1;
                      setHistoryPage(page);
                      load(staff, page).catch((e) => setError(e.message));
                    }}
                  >
                    Previous
                  </button>
                  <span>Page {historyPage + 1}</span>
                  <button
                    disabled={transactions.length < 50 || loading}
                    onClick={() => {
                      const page = historyPage + 1;
                      setHistoryPage(page);
                      load(staff, page).catch((e) => setError(e.message));
                    }}
                  >
                    Next
                  </button>
                </div>
              )}
            </Section>
          )}

          {!staff && tab === "Cards" && (
            <Section
              title="Your everyday companion"
              subtitle="Sandbox virtual cards. These cards cannot make real purchases."
              action={
                <button className="secondary" onClick={() => open("card")}>
                  <Plus size={16} /> Create sandbox card
                </button>
              }
            >
              <div className="cards-grid">
                {cards.map((card) => (
                  <div key={card.id}>
                    <div
                      className={`bank-card ${card.card_status === "frozen" ? "frozen" : ""}`}
                    >
                      <div>
                        <strong>MORROW</strong>
                        <span>VIRTUAL · SANDBOX</span>
                      </div>
                      <div className="chip" />
                      <div className="card-number">
                        •••• &nbsp; •••• &nbsp; •••• &nbsp; {card.card_last_4}
                      </div>
                      <div className="card-footer">
                        <span>{card.card_holder_name}</span>
                        <span>
                          {String(card.expiry_month).padStart(2, "0")}/
                          {String(card.expiry_year).slice(-2)}
                        </span>
                      </div>
                    </div>
                    <div className="card-controls">
                      <Badge value={card.card_status} />
                      {card.card_status !== "cancelled" && (
                        <button
                          disabled={busy}
                          className="text-button"
                          onClick={() =>
                            action(
                              () =>
                                api(`/cards/${card.id}/status`, {
                                  method: "PATCH",
                                  body: JSON.stringify({
                                    status:
                                      card.card_status === "active"
                                        ? "frozen"
                                        : "active",
                                  }),
                                }),
                              "Card updated.",
                            )
                          }
                        >
                          {card.card_status === "active"
                            ? "Freeze card"
                            : "Unfreeze card"}
                        </button>
                      )}
                    </div>
                    <CardControls card={card} updated={() => load(false)} />
                  </div>
                ))}
              </div>
              {!cards.length && (
                <Empty
                  icon={<CreditCard />}
                  title="Meet your virtual card"
                  text="Create a sandbox card linked to an active account."
                />
              )}
            </Section>
          )}

          {!staff && tab === "Identity" && (
            <section className="identity-panel">
              <div className="large-icon">
                <ShieldCheck size={34} />
              </div>
              <Badge value={person.kyc_status || "pending"} />
              <h2>
                {person.kyc_status === "verified"
                  ? "You’re all set."
                  : "Let’s make it official."}
              </h2>
              <p>
                {person.kyc_status === "verified"
                  ? "Your identity has been verified. You can open accounts and move money."
                  : "Submit your identity document details for a staff member to review. Verification is required before opening an account."}
              </p>
              {person.kyc_status !== "verified" && (
                <button className="primary" onClick={() => open("kyc")}>
                  Submit identity details <ArrowRight size={17} />
                </button>
              )}
            </section>
          )}

          {staff && tab === "Overview" && (
            <>
              <div className="stats-grid">
                {Object.entries(summary).map(([key, value]) => (
                  <div className="stat" key={key}>
                    <span>{key.replaceAll("_", " ")}</span>
                    <strong>{value}</strong>
                    <span className="stat-note">Current workspace</span>
                  </div>
                ))}
              </div>
              <Section
                title="Your review queue"
                subtitle="Clear decisions, with an audit trail."
              >
                <div className="review-overview">
                  <ShieldCheck size={32} />
                  <div>
                    <h3>
                      {(summary.pending_transfers || 0) +
                        (summary.pending_kyc || 0)}{" "}
                      items need attention
                    </h3>
                    <p>
                      Identity submissions and transfers awaiting a compliance
                      decision.
                    </p>
                  </div>
                  {person.role !== "support" && (
                    <button
                      className="primary"
                      onClick={() => setTab("Reviews")}
                    >
                      Open reviews <ArrowRight size={17} />
                    </button>
                  )}
                </div>
              </Section>
            </>
          )}

          {staff &&
            [
              "Customers",
              "Accounts",
              "Reviews",
              "AML checks",
              "Audit log",
            ].includes(tab) && (
              <Operations key={tab} section={tab} role={person.role} />
            )}
          <footer className="page-footer">
            <span>
              <ShieldCheck size={14} /> Built around a clear record of your
              money.
            </span>
            <span>
              Morrow Banking Core <span className="footer-dot">·</span> Sandbox
              environment
            </span>
          </footer>
        </div>
      </main>
      {modal && (
        <div className="modal-backdrop" onClick={() => !busy && setModal(null)}>
          <section
            ref={dialogRef}
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="modal-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-heading">
              <div>
                <span className="eyebrow">YOUR NEXT MOVE</span>
                <h2 id="modal-title">
                  {
                    {
                      transfer: "Move money",
                      account: "Open an account",
                      card: "Create a sandbox card",
                      kyc: "Verify your identity",
                      profile: "Your profile",
                      help: "A clearer kind of banking",
                    }[modal]
                  }
                </h2>
              </div>
              <button
                className="icon-button"
                aria-label="Close dialog"
                disabled={busy}
                onClick={() => setModal(null)}
              >
                <X size={22} />
              </button>
            </div>
            {error && (
              <div role="alert" className="alert error">
                {error}
              </div>
            )}
            {modal === "help" ? (
              <div className="help-content">
                <p>
                  This workspace demonstrates ledger-based banking. Create an
                  account, verify your identity, and transfer between verified
                  accounts in the same currency.
                </p>
                <p>
                  Every transfer has a 1% fee. Transfers of 10,000 or more wait
                  for staff review. Pending transfers do not reserve funds;
                  availability is checked again on approval.
                </p>
                <p>
                  Cards are sandbox metadata. No real payment network, external
                  deposits, or currency exchange is connected.
                </p>
              </div>
            ) : (
              <form onSubmit={submit}>
                {modal === "transfer" && (
                  <>
                    <label>
                      From account
                      <select name="from_account_id" required>
                        {accounts
                          .filter((a) => a.account_status === "active")
                          .map((a) => (
                            <option key={a.id} value={a.id}>
                              {a.account_name} ·{" "}
                              {money(a.balance || 0, a.currency_code)}
                            </option>
                          ))}
                      </select>
                    </label>
                    <label>
                      Recipient account ID
                      <input
                        name="to_account_id"
                        required
                        placeholder="Paste the recipient’s account UUID"
                        list="own-accounts"
                      />
                      <datalist id="own-accounts">
                        {accounts.map((a) => (
                          <option key={a.id} value={a.id}>
                            {a.account_name}
                          </option>
                        ))}
                      </datalist>
                      <small>
                        Find your account ID under Accounts. Use the same
                        currency.
                      </small>
                    </label>
                    <label>
                      Amount
                      <input
                        name="amount"
                        type="number"
                        min="0.01"
                        step="0.01"
                        max="1000000"
                        placeholder="0.00"
                        required
                      />
                    </label>
                    <label>
                      Note
                      <input
                        name="description"
                        maxLength={200}
                        defaultValue="Transfer"
                        required
                      />
                    </label>
                    <div className="form-note">
                      <ShieldCheck size={18} />
                      <span>
                        A 1% fee is added to your transfer. Amounts of 10,000 or
                        more require review.
                      </span>
                    </div>
                  </>
                )}
                {modal === "account" && (
                  <>
                    <label>
                      Account name
                      <input
                        name="account_name"
                        placeholder="e.g. Rainy day savings"
                        maxLength={100}
                        required
                      />
                    </label>
                    <div className="form-grid">
                      <label>
                        Account type
                        <select name="account_type">
                          <option value="checking">Checking</option>
                          <option value="savings">Savings</option>
                        </select>
                      </label>
                      <label>
                        Currency
                        <select name="currency_code">
                          {["CAD", "USD", "GBP", "EUR"].map((c) => (
                            <option key={c}>{c}</option>
                          ))}
                        </select>
                      </label>
                    </div>
                    <p className="form-note">
                      Identity verification is required. New accounts start at
                      zero.
                    </p>
                  </>
                )}
                {modal === "card" && (
                  <>
                    <label>
                      Linked account
                      <select name="account_id" required>
                        {accounts
                          .filter((a) => a.account_status === "active")
                          .map((a) => (
                            <option key={a.id} value={a.id}>
                              {a.account_name}
                            </option>
                          ))}
                      </select>
                    </label>
                    <label>
                      Name on card
                      <input
                        name="card_holder_name"
                        defaultValue={`${person.first_name} ${person.last_name}`}
                        maxLength={100}
                        required
                      />
                    </label>
                    <p className="form-note">
                      A sandbox card has no real card number and cannot make
                      purchases.
                    </p>
                  </>
                )}
                {modal === "kyc" && (
                  <>
                    <label>
                      Document type
                      <select name="document_type">
                        <option value="passport">Passport</option>
                        <option value="national_id">National ID</option>
                        <option value="driver_license">Driver’s licence</option>
                        <option value="id_card">ID card</option>
                      </select>
                    </label>
                    <label>
                      Document number
                      <input name="document_number" required maxLength={100} />
                    </label>
                    <label>
                      Document front (PNG, JPEG or PDF, up to 5 MB)
                      <input
                        name="document_front_url"
                        type="file"
                        accept="image/png,image/jpeg,application/pdf"
                        required
                      />
                    </label>
                    <label>
                      Document back (optional)
                      <input
                        name="document_back_url"
                        type="file"
                        accept="image/png,image/jpeg,application/pdf"
                      />
                    </label>
                    <label>
                      Selfie (PNG or JPEG, up to 5 MB)
                      <input
                        name="selfie_url"
                        type="file"
                        accept="image/png,image/jpeg"
                        required
                      />
                    </label>
                    <label>
                      Expiry date
                      <input name="expiry_date" type="date" />
                    </label>
                    <p className="form-note">
                      Use test identity details and files in this sandbox. Files
                      are encrypted at rest; staff review is manual.
                    </p>
                  </>
                )}
                {modal === "profile" && (
                  <>
                    <label>
                      First name
                      <input
                        name="first_name"
                        defaultValue={person.first_name}
                        required
                        maxLength={100}
                      />
                    </label>
                    <label>
                      Last name
                      <input
                        name="last_name"
                        defaultValue={person.last_name}
                        required
                        maxLength={100}
                      />
                    </label>
                    <label>
                      Email
                      <input value={person.email} disabled readOnly />
                    </label>
                  </>
                )}
                <button
                  className="primary full"
                  disabled={
                    busy ||
                    ((modal === "transfer" || modal === "card") &&
                      !accounts.length)
                  }
                >
                  {busy
                    ? "Working…"
                    : modal === "transfer"
                      ? "Confirm transfer"
                      : modal === "kyc"
                        ? "Submit for review"
                        : "Save & continue"}
                  {!busy && <ArrowRight size={17} />}
                </button>
              </form>
            )}
          </section>
        </div>
      )}
    </div>
  );
}

function Section({
  title,
  subtitle,
  action,
  children,
}: {
  title: string;
  subtitle: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="section">
      <div className="section-heading">
        <div>
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
function Empty({
  icon,
  title,
  text,
  action,
}: {
  icon: React.ReactNode;
  title: string;
  text: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="empty">
      <span>{icon}</span>
      <h3>{title}</h3>
      <p>{text}</p>
      {action}
    </div>
  );
}
function AccountTile({
  account: a,
  hidden,
  onSelect,
}: {
  account: Account;
  hidden: boolean;
  onSelect?: () => void;
}) {
  return (
    <article className="account-tile">
      <div className="account-top">
        <span
          className={`account-icon ${a.account_type === "savings" ? "purple" : ""}`}
        >
          {a.account_type === "savings" ? (
            <Landmark size={20} />
          ) : (
            <Wallet size={20} />
          )}
        </span>
        <Badge value={a.account_status} />
      </div>
      <h3>{a.account_name}</h3>
      <div className="account-number">
        {a.account_type} <span>·</span> •••• {a.account_number.slice(-4)}
      </div>
      <div className="account-bottom">
        <strong>
          {hidden ? "••,•••.••" : money(a.balance || 0, a.currency_code)}
        </strong>
        <span>{a.currency_code}</span>
        {onSelect && (
          <button aria-label={`View ${a.account_name}`} onClick={onSelect}>
            <ArrowUpRight size={18} />
          </button>
        )}
      </div>
    </article>
  );
}
function TransactionTable({
  rows,
  owned,
  staff,
}: {
  rows: Transaction[];
  owned: Set<string>;
  staff: boolean;
}) {
  return rows.length ? (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Transaction</th>
            <th>Date</th>
            <th>Status</th>
            <th className="right">Amount</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((t) => {
            const incoming =
              owned.has(t.to_account_id || "") && !owned.has(t.from_account_id);
            const own =
              owned.has(t.to_account_id || "") && owned.has(t.from_account_id);
            return (
              <tr key={t.id}>
                <td>
                  <div className="transaction-name">
                    <span
                      className={`transaction-icon ${incoming ? "incoming" : ""}`}
                    >
                      {incoming ? (
                        <ArrowDownLeft size={19} />
                      ) : (
                        <ArrowUpRight size={19} />
                      )}
                    </span>
                    <div>
                      <strong>
                        {t.transaction_type === "deposit"
                          ? "Opening funds"
                          : t.transaction_type === "reversal"
                            ? "Reversal"
                            : own
                              ? "Between your accounts"
                              : incoming
                                ? "Transfer received"
                                : "Transfer sent"}
                      </strong>
                      <small>{t.reference_number || t.id.slice(0, 12)}</small>
                    </div>
                  </div>
                </td>
                <td>{date(t.transaction_date)}</td>
                <td>
                  <Badge value={t.status} />
                </td>
                <td className={`right amount ${incoming ? "positive" : ""}`}>
                  {!staff
                    ? incoming
                      ? "+"
                      : t.transaction_type === "reversal"
                        ? ""
                        : "−"
                    : ""}
                  {money(t.amount, t.currency_code)}
                  <small>
                    {t.currency_code}
                    {Number(t.fee_amount) > 0
                      ? ` · ${money(t.fee_amount, t.currency_code)} fee`
                      : ""}
                  </small>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  ) : (
    <Empty
      icon={<ArrowLeftRight />}
      title="A fresh start"
      text="Your transactions will appear here as you move money."
    />
  );
}

function Login({ onLogin }: { onLogin: (staff: boolean) => Promise<void> }) {
  const [mode, setMode] = useState<"login" | "signup" | "staff">("login");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    const data = Object.fromEntries(new FormData(event.currentTarget));
    try {
      const tokens = await post<{
        access_token: string;
        refresh_token: string;
      }>(
        mode === "signup"
          ? "/auth/signup"
          : mode === "staff"
            ? "/auth/admin/login"
            : "/auth/login",
        data,
      );
      setTokens(tokens);
      await onLogin(mode === "staff");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="login-page">
      <section className="login-art">
        <a className="brand" href="/">
          MORROW<span>®</span>
        </a>
        <div className="login-story">
          <span className="pill">MORE LIFE. LESS BANKING.</span>
          <h1>
            Make room <br />
            for what
            <br />
            <em>moves you.</em>
          </h1>
          <p>
            A clear view of your money.
            <br />A little more freedom for everything else.
          </p>
          <div className="login-card">
            <span>MORROW</span>
            <div className="chip" />
            <strong>YOUR NEXT CHAPTER</strong>
            <small>Everyday possibilities.</small>
          </div>
        </div>
        <div className="login-foot">
          Your money. Your pace. Your possibilities.
        </div>
        <div className="art-ring" />
      </section>
      <section className="login-form-panel">
        <div className="login-top">
          <span className="sandbox">
            <i /> BANKING SANDBOX
          </span>
          <button
            className="text-button"
            onClick={() => {
              setMode(mode === "staff" ? "login" : "staff");
              setError("");
            }}
          >
            {mode === "staff" ? "Personal banking" : "Staff sign in"}{" "}
            <ArrowUpRight size={15} />
          </button>
        </div>
        <div className="login-form">
          <span className="eyebrow">LET’S GET YOU SETTLED IN</span>
          <h2>
            {mode === "signup"
              ? "A fresh start."
              : mode === "staff"
                ? "Hello, team."
                : "Good to see you."}
          </h2>
          <p>
            {mode === "signup"
              ? "Create your account. Your next chapter starts here."
              : mode === "staff"
                ? "Sign in to your operations workspace."
                : "Sign in and pick up right where you left off."}
          </p>
          {error && (
            <div role="alert" className="alert error">
              {error}
            </div>
          )}
          <form onSubmit={submit}>
            {mode === "signup" && (
              <div className="form-grid">
                <label>
                  First name
                  <input
                    name="first_name"
                    required
                    maxLength={100}
                    autoComplete="given-name"
                  />
                </label>
                <label>
                  Last name
                  <input
                    name="last_name"
                    required
                    maxLength={100}
                    autoComplete="family-name"
                  />
                </label>
              </div>
            )}
            <label>
              Email address
              <input
                name="email"
                type="email"
                placeholder="you@example.com"
                autoComplete="email"
                required
              />
            </label>
            <label>
              Password
              <input
                name="password"
                type="password"
                minLength={mode === "signup" ? 12 : 1}
                maxLength={128}
                placeholder={
                  mode === "signup"
                    ? "At least 12 characters"
                    : "Enter your password"
                }
                autoComplete={
                  mode === "signup" ? "new-password" : "current-password"
                }
                required
              />
            </label>
            <button className="primary full" disabled={busy}>
              {busy
                ? "Connecting…"
                : mode === "signup"
                  ? "Create account"
                  : "Sign in"}
              <ArrowRight size={18} />
            </button>
          </form>
          {mode !== "staff" && (
            <p className="signup-switch">
              {mode === "signup"
                ? "Already part of the family?"
                : "New around here?"}{" "}
              <button
                onClick={() => {
                  setMode(mode === "signup" ? "login" : "signup");
                  setError("");
                }}
              >
                {mode === "signup" ? "Sign in" : "Create an account"}
              </button>
            </p>
          )}
          <div className="login-security">
            <ShieldCheck size={18} />
            <span>
              Your session stays in this browser tab.
              <br />
              Sign in again after refreshing or closing it.
            </span>
          </div>
        </div>
        <div className="login-bottom">
          A development banking workspace. No real money moves.
        </div>
      </section>
    </div>
  );
}
