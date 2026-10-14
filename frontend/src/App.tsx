import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, type AgentEvent, type AgentName, type Cash, type PaymentRequest, type RateApproval, type TeamReport, type Ticket } from './api'
import { AGENTS, AGENT_ORDER, TICKET_KIND, chequeWords, money, stampDate, toolLabel } from './desk'
import { Avatar, FeedItem } from './Feed'

interface Run {
  ticketId: number
  startAfter: number // last audit index before the run began
  runId?: string
  report?: TeamReport
  error?: string
  startedAt: number
  finishedAt?: number
}

interface Paid {
  id: number
  payee: string
  amount: number
  by: string
  at: number
}

type Cheque = PaymentRequest & { fromTicket: number }

const RUNS_KEY = 'cc-desk-runs'
const PAID_KEY = 'cc-desk-paid'
const NAME_KEY = 'cc-desk-signer'

function load<T>(key: string, fallback: T): T {
  try {
    return (JSON.parse(localStorage.getItem(key) ?? 'null') as T) ?? fallback
  } catch {
    return fallback
  }
}

const payKey = (p: PaymentRequest) => `${p.kind}:${p.ref_id ?? p.payee}:${p.amount}`
const rateKey = (r: RateApproval) => `rate:${r.ticket_id}:${r.sku}:${r.discount_pct}`
const reduceMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches

/** Rolls a number from its old value to the new one (ease-out cubic). */
function useRolling(target: number | null, ms = 650): number | null {
  const [shown, setShown] = useState(target)
  const from = useRef(target)
  useEffect(() => {
    if (target === null) return
    const start = from.current
    from.current = target
    if (start === null || start === target || reduceMotion()) {
      setShown(target)
      return
    }
    const t0 = performance.now()
    let raf = 0
    const tick = (now: number) => {
      const k = Math.min(1, (now - t0) / ms)
      setShown(start + (target - start) * (1 - (1 - k) ** 3))
      if (k < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target, ms])
  return shown
}

function useNow(active: boolean) {
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    if (!active) return
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [active])
  return now
}

const elapsed = (ms: number) => {
  const s = Math.max(0, Math.round(ms / 1000))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

export default function App() {
  const [today, setToday] = useState('')
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [cash, setCash] = useState<Cash | null>(null)
  const [drop, setDrop] = useState<number | null>(null)
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [runs, setRuns] = useState<Record<number, Run>>(() => load(RUNS_KEY, {}))
  const [paid, setPaid] = useState<Record<string, Paid>>(() => load(PAID_KEY, {}))
  const [selected, setSelected] = useState<number | null>(null)
  const [running, setRunning] = useState<number | null>(null)
  const [signer, setSigner] = useState(() => localStorage.getItem(NAME_KEY) ?? '')
  const [paying, setPaying] = useState<string | null>(null)
  const [tearing, setTearing] = useState<string | null>(null)
  const [toast, setToast] = useState<{ tone: 'ok' | 'bad'; text: string } | null>(null)
  const [offline, setOffline] = useState(false)
  const [newBelow, setNewBelow] = useState(false)
  const lastIndex = useRef(-1)
  const spool = useRef<HTMLDivElement>(null)
  const pinned = useRef(true)
  const now = useNow(running !== null)
  const balance = useRolling(cash?.balance ?? null)

  useEffect(() => localStorage.setItem(RUNS_KEY, JSON.stringify(runs)), [runs])
  useEffect(() => localStorage.setItem(PAID_KEY, JSON.stringify(paid)), [paid])
  useEffect(() => localStorage.setItem(NAME_KEY, signer), [signer])
  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(null), 5000)
    return () => clearTimeout(t)
  }, [toast])

  const refreshBoard = useCallback(async () => {
    try {
      const [t, c] = await Promise.all([api.tickets(), api.cash()])
      setToday(t.date_today)
      setTickets(t.tickets)
      setCash(c)
      setOffline(false)
    } catch {
      setOffline(true)
    }
  }, [])

  const pullEvents = useCallback(async () => {
    try {
      const { events: fresh } = await api.events(lastIndex.current, 5000)
      if (fresh.length) {
        lastIndex.current = fresh[fresh.length - 1].index
        setEvents((prev) => [...prev, ...fresh])
      }
    } catch {
      /* refreshBoard reports offline */
    }
  }, [])

  // Board + cash every 5s; while the team runs, events + board every 1.2s.
  useEffect(() => {
    refreshBoard()
    pullEvents()
    const id = setInterval(refreshBoard, 5000)
    return () => clearInterval(id)
  }, [refreshBoard, pullEvents])
  useEffect(() => {
    if (running === null) return
    const id = setInterval(() => {
      pullEvents()
      refreshBoard()
    }, 1200)
    return () => clearInterval(id)
  }, [running, pullEvents, refreshBoard])

  // A live run learns its run_id from the Boss's first audit entry.
  useEffect(() => {
    if (running === null) return
    const run = runs[running]
    if (!run || run.runId) return
    const first = events.find((e) => e.index > run.startAfter && e.run_id && e.agent === 'boss')
    if (first) setRuns((r) => ({ ...r, [running]: { ...r[running], runId: first.run_id! } }))
  }, [events, running, runs])

  const startRun = async (ticketId: number) => {
    if (running !== null) return
    setSelected(ticketId)
    pinned.current = true
    await pullEvents()
    const startAfter = lastIndex.current
    setRuns((r) => ({ ...r, [ticketId]: { ticketId, startAfter, startedAt: Date.now() } }))
    setRunning(ticketId)
    try {
      const res = await api.run(ticketId)
      setRuns((r) => ({ ...r, [ticketId]: { ...r[ticketId], runId: res.run_id, report: res.report, finishedAt: Date.now() } }))
      const asks = res.report.payment_queue.length + (res.report.rate_approvals?.length ?? 0)
      const head = res.status === 'resolved' ? `Work order #${ticketId} resolved.` : `Team finished #${ticketId}: ${res.status.replace(/_/g, ' ')}.`
      const tail = asks ? ` ${asks} item${asks > 1 ? 's' : ''} waiting for your signature, then run the team again.` : ''
      setToast({ tone: 'ok', text: head + tail })
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      setRuns((r) => ({ ...r, [ticketId]: { ...r[ticketId], error: msg, finishedAt: Date.now() } }))
      setToast({ tone: 'bad', text: msg })
    } finally {
      setRunning(null)
      await pullEvents()
      await refreshBoard()
    }
  }

  const approve = async (p: Cheque) => {
    const name = signer.trim()
    if (!name) return
    const key = payKey(p)
    setPaying(key)
    try {
      const res = await api.approve(p, name)
      setTearing(key)
      setDrop(res.balance_before - res.balance_after)
      setCash((c) => (c ? { ...c, balance: res.balance_after } : c))
      setTimeout(() => {
        setPaid((x) => ({ ...x, [key]: { id: res.payment_id, payee: p.payee, amount: p.amount, by: name, at: Date.now() } }))
        setTearing(null)
      }, 320)
      setTimeout(() => setDrop(null), 2200)
      setToast({ tone: 'ok', text: res.effect })
      refreshBoard()
    } catch (err) {
      setToast({ tone: 'bad', text: err instanceof Error ? err.message : String(err) })
    } finally {
      setPaying(null)
    }
  }

  const approveRate = async (r: RateApproval) => {
    const name = signer.trim()
    if (!name) return
    const key = rateKey(r)
    setPaying(key)
    try {
      const res = await api.approveRate(r, name)
      setPaid((x) => ({ ...x, [key]: { id: 0, payee: `${r.discount_pct}% group rate`, amount: 0, by: name, at: Date.now() } }))
      setToast({ tone: 'ok', text: `${res.effect} Run the team again to close #${r.ticket_id}.` })
      refreshBoard()
    } catch (err) {
      setToast({ tone: 'bad', text: err instanceof Error ? err.message : String(err) })
    } finally {
      setPaying(null)
    }
  }

  const reset = async () => {
    if (running !== null) return
    if (!confirm('Reset the shop to its original data? Cash goes back to the start and this desk forgets its runs and cheques.')) return
    try {
      await api.reset()
      setRuns({})
      setPaid({})
      setSelected(null)
      setToast({ tone: 'ok', text: 'Fresh shift. The shop database is back to its original values.' })
      await refreshBoard()
      await pullEvents()
    } catch (err) {
      setToast({ tone: 'bad', text: err instanceof Error ? err.message : String(err) })
    }
  }

  const run = selected !== null ? runs[selected] : undefined
  const ticket = tickets.find((t) => t.id === selected)
  const live = running !== null && running === selected

  const runEvents = useMemo(() => {
    if (!run) return []
    return events.filter((e) => (run.runId ? e.run_id === run.runId : e.index > run.startAfter && e.run_id !== null))
  }, [events, run])

  // Keep the spool scrolled to the newest line unless the reader scrolled up.
  useEffect(() => {
    const el = spool.current
    if (!el) return
    if (pinned.current) el.scrollTop = el.scrollHeight
    else setNewBelow(true)
  }, [runEvents.length])
  const onScroll = () => {
    const el = spool.current
    if (!el) return
    pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80
    if (pinned.current) setNewBelow(false)
  }

  const agentNow = useMemo(() => {
    const out: Partial<Record<AgentName, AgentEvent>> = {}
    for (const e of runEvents) if (e.agent !== 'human') out[e.agent] = e
    return out
  }, [runEvents])

  const summaries = useMemo(() => {
    const out: Partial<Record<AgentName, string>> = {}
    for (const e of runEvents) if (e.kind === 'final_output' && e.agent !== 'human' && e.said) out[e.agent] = e.said
    if (run?.report) out.boss = run.report.run_summary
    return out
  }, [runEvents, run])

  const cheques = useMemo(() => {
    const seen = new Map<string, Cheque>()
    for (const r of Object.values(runs))
      for (const p of r.report?.payment_queue ?? []) if (!seen.has(payKey(p))) seen.set(payKey(p), { ...p, fromTicket: r.ticketId })
    return [...seen.values()].sort((a, b) => a.priority - b.priority)
  }, [runs])
  const pending = cheques.filter((p) => !(payKey(p) in paid))
  const rates = useMemo(() => {
    const seen = new Map<string, RateApproval>()
    for (const r of Object.values(runs)) for (const x of r.report?.rate_approvals ?? []) seen.set(rateKey(x), x)
    return [...seen.values()]
  }, [runs])
  const pendingRates = rates.filter((r) => !(rateKey(r) in paid))
  const pendingTotal = pending.reduce((s, p) => s + p.amount, 0)
  const ledger = Object.values(paid).filter((l) => l.amount > 0).sort((a, b) => b.at - a.at).slice(0, 3)

  // Resolved only when the DB says so (Boss's final status, or rent paid), so the board matches GET /tickets.
  const isResolved = (t: Ticket) => t.state === 'resolved'
  const openTickets = tickets.filter((t) => !isResolved(t))
  const doneTickets = tickets.filter(isResolved)
  const allDone = tickets.length > 0 && openTickets.length === 0

  const ticketCard = (t: Ticket, i: number) => {
    const resolved = isResolved(t)
    const working = running === t.id
    const needsSig = pending.some((p) => p.unblocks_tickets.includes(t.id) || p.fromTicket === t.id) || pendingRates.some((r) => r.ticket_id === t.id)
    return (
      <li key={t.id}>
        <article
          className={`order ${selected === t.id ? 'selected' : ''} ${working ? 'working' : ''} ${resolved ? 'resolved' : ''}`}
          style={{ '--tilt': `${i % 2 ? 0.4 : -0.4}deg` } as React.CSSProperties}
          onClick={() => setSelected(t.id)}
          tabIndex={0}
          onKeyDown={(e) => e.key === 'Enter' && setSelected(t.id)}
        >
          <span className="punch" aria-hidden />
          <div className="order-top">
            <span className="mono order-no">#{t.id}</span>
            <span className="label">{TICKET_KIND[t.type] ?? t.type}</span>
          </div>
          <h3>{t.subject}</h3>
          <p className="order-from">from {t.requester}</p>
          {t.sku && (
            <p className="mono order-detail">
              {[t.sku, t.size && `size ${t.size}`, t.qty && `× ${t.qty}`].filter(Boolean).join(' · ')}
            </p>
          )}
          {working && <p className="mono order-timer">Team at work · {elapsed(now - (runs[t.id]?.startedAt ?? now))}</p>}
          {needsSig && !working && <p className="order-sig"><span>✎ Needs your signature</span></p>}
          {!resolved && !working && (
            <button
              className="btn primary"
              disabled={running !== null || offline}
              onClick={(e) => {
                e.stopPropagation()
                startRun(t.id)
              }}
            >
              Start the team
            </button>
          )}
          {resolved && <span className="stamp" aria-label="Resolved">Resolved<small>{stampDate(today)}</small></span>}
          {working && <span className="print-head" aria-hidden />}
        </article>
      </li>
    )
  }

  return (
    <div className="desk">
      <header className="masthead">
        <span className="reg reg-l" aria-hidden />
        <span className="reg reg-r" aria-hidden />
        <div className="brand">
          <span className="brand-mark" aria-hidden>CC</span>
          <div>
            <h1>Campus Customs <span className="thin">· Agent Desk</span></h1>
            <p className="tagline">Back room, Chapel St · printed in New Haven</p>
          </div>
        </div>
        <div className="masthead-meta">
          <div className="meta">
            <span className="label">Shop date</span>
            <span className="mono">{today || '—'}</span>
          </div>
          <div className="meta">
            <span className="label">Closed</span>
            <span className="mono">{doneTickets.length} / {tickets.length || 3}</span>
          </div>
          <span className={`lamp ${offline ? 'down' : running !== null ? 'busy' : 'up'}`}>
            {offline ? 'Backend offline — start uvicorn on :8000' : running !== null ? 'Team at work' : 'Desk open'}
          </span>
          <button className="btn ghost" onClick={reset} disabled={running !== null || offline}>
            Reset shop
          </button>
        </div>
      </header>

      <main className="workbench">
        {/* ---------- Order rail ---------- */}
        <section className="rail" aria-label="Work orders">
          <h2 className="section">Work orders</h2>
          <ul className="orders">
            {openTickets.map(ticketCard)}
            {doneTickets.length > 0 && <li className="divider"><span>Done today</span></li>}
            {doneTickets.map((t, i) => ticketCard(t, i + openTickets.length))}
            {!tickets.length && <li className="empty">{offline ? 'Waiting for the backend on :8000…' : 'Pulling work orders…'}</li>}
          </ul>
          {allDone && <p className="wrap-note">That’s a wrap for {stampDate(today)}. Lock up on your way out.</p>}
        </section>

        {/* ---------- Spool ---------- */}
        <section className="spool" aria-label="Agent activity">
          <div className="spool-head">
            <div>
              <span className="label">{ticket ? `${TICKET_KIND[ticket.type] ?? ticket.type} · from ${ticket.requester}` : 'The spool'}</span>
              <h2 className="spool-title">
                {ticket ? <><span className="mono">#{ticket.id}</span> {ticket.subject}</> : 'Pick a work order'}
              </h2>
            </div>
            {ticket && !live && (
              <button className="btn primary" disabled={running !== null || offline} onClick={() => startRun(ticket.id)}>
                {run ? 'Run the team again' : 'Start the team'}
              </button>
            )}
            {live && <span className="mono run-clock">{elapsed(now - (run?.startedAt ?? now))}</span>}
          </div>

          <div className="roster">
            {AGENT_ORDER.map((a) => {
              const last = agentNow[a]
              const state = !last ? 'idle' : last.kind === 'final_output' || !live ? 'done' : 'busy'
              return (
                <div key={a} className={`chip ${state}`} style={{ '--agent': AGENTS[a].color } as React.CSSProperties} title={AGENTS[a].role}>
                  <Avatar agent={a} />
                  <div>
                    <strong>{AGENTS[a].name}</strong>
                    <span>{crewLine(last, state)}</span>
                  </div>
                  <i className="dot" aria-hidden />
                </div>
              )
            })}
          </div>

          <div className="paper" ref={spool} onScroll={onScroll} role="log" aria-live="polite">
            {!ticket && (
              <div className="idle">
                <TeeOnPress />
                <p className="big">Pick a work order from the rail.</p>
                <p>The team’s waiting by the heat press.</p>
              </div>
            )}
            {ticket && !run && (
              <div className="idle">
                <TeeOnPress />
                <p className="big">Five agents on shift.</p>
                <p>Press <b>Start the team</b> and watch the spool. The Boss reads the ticket first and only calls in who it needs.</p>
              </div>
            )}
            {run && runEvents.length === 0 && !run.error && <div className="idle"><p className="big">Boss is reading the ticket…</p></div>}
            {runEvents.map((e) => <FeedItem key={e.index} e={e} />)}
            {run?.error && <div className="msg error"><p>Run failed: {run.error}</p></div>}
            {live && <div className="typing" aria-label="agents working"><i /><i /><i /></div>}

            {run?.report && ticket && (
              <section className="debrief" aria-label="Debrief">
                <h3 className="section">Debrief · who did what on #{ticket.id}</h3>
                {AGENT_ORDER.filter((a) => summaries[a]).map((a) => (
                  <div key={a} className="debrief-row" style={{ '--agent': AGENTS[a].color } as React.CSSProperties}>
                    <Avatar agent={a} small />
                    <div>
                      <strong>{AGENTS[a].name}</strong>
                      <p>{summaries[a]}</p>
                    </div>
                  </div>
                ))}
                {run.report.tickets.filter((o) => o.ticket_id === ticket.id).map((o) => (
                  <div key={o.ticket_id} className="decision">
                    <span className="label">Decision · owner {AGENTS[o.owner]?.name ?? o.owner}</span>
                    <p>{o.decision}</p>
                    {o.customer_message && (
                      <>
                        <span className="label">Reply to {ticket.requester}</span>
                        <blockquote>{o.customer_message}</blockquote>
                      </>
                    )}
                  </div>
                ))}
                {(run.report.deferred.length > 0 || run.report.risks.length > 0) && (
                  <div className="decision">
                    <span className="label">Held back · watch out</span>
                    <ul>{[...run.report.deferred, ...run.report.risks].map((x, i) => <li key={i}>{x}</li>)}</ul>
                  </div>
                )}
              </section>
            )}
          </div>
          {newBelow && (
            <button className="new-below" onClick={() => { pinned.current = true; setNewBelow(false); spool.current?.scrollTo({ top: spool.current.scrollHeight, behavior: 'smooth' }) }}>
              New lines ↓
            </button>
          )}
        </section>

        {/* ---------- Till ---------- */}
        <aside className="till" aria-label="Cash and approvals">
          <div className={`balance ${drop ? 'dropping' : ''}`}>
            <span className="label">Checking · Elm City Savings</span>
            <span className="figure">{balance === null ? '—' : money(balance)}</span>
            {drop && <span className="minus mono">−{money(drop)}</span>}
            <span className="ink-line" aria-hidden />
            <span className="pending">
              {pending.length ? <>Pending signatures: <b className="mono">{money(pendingTotal)}</b> <em>(not deducted)</em></> : 'Only moves when you sign a cheque.'}
            </span>
            {ledger.length > 0 && (
              <ul className="mini-ledger mono">
                {ledger.map((l) => (
                  <li key={l.id}><span>{stampDate(today)}</span><span>{l.payee}</span><span>−{money(l.amount)}</span></li>
                ))}
              </ul>
            )}
          </div>

          <div className="tray-head">
            <h2 className="section">Cheque tray</h2>
            {pending.length + pendingRates.length > 0 && <span className="badge">{pending.length + pendingRates.length}</span>}
          </div>
          <label className="signature">
            <span className="label">Signed by</span>
            <input value={signer} onChange={(e) => setSigner(e.target.value)} placeholder="Sign your name" autoComplete="off" />
          </label>

          <div className="tray">
            {rates.map((r) => {
              const key = rateKey(r)
              const done = paid[key]
              return (
                <article key={key} className={`cheque rate ${done ? 'paid' : ''}`}>
                  <div className="cheque-top mono">
                    <span>Rate slip · #{r.ticket_id}</span>
                    <span>{today}</span>
                  </div>
                  <span className="label">Group rate for approval · no cash moves</span>
                  <div className="cheque-line">
                    <span className="payee">{r.qty} × {r.sku} at {r.discount_pct}% off</span>
                    <span className="amt-box mono">{money(r.unit_price)}</span>
                  </div>
                  <p className="words">each · order margin {money(r.order_margin)}</p>
                  <p className="reason">{r.reason}</p>
                  {done ? (
                    <div className="cheque-foot">
                      <span className="signed">{done.by}</span>
                      <span className="paid-stamp">Rate approved</span>
                    </div>
                  ) : (
                    <div className="cheque-foot">
                      <span className="sig-line">{signer || ' '}</span>
                      <button className="btn primary" disabled={!signer.trim() || paying !== null || running !== null} onClick={() => approveRate(r)}>
                        {paying === key ? 'Signing…' : 'Approve rate'}
                      </button>
                    </div>
                  )}
                </article>
              )
            })}
            {cheques.length === 0 && rates.length === 0 && <p className="empty">No cheques to sign. Balance is safe — for now.</p>}
            {cheques.map((p) => {
              const key = payKey(p)
              const done = paid[key]
              const short = !done && cash ? p.amount > cash.balance : false
              return (
                <article key={key} className={`cheque ${done ? 'paid' : ''} ${tearing === key ? 'tearing' : ''}`}>
                  <div className="cheque-top mono">
                    <span>No. {p.fromTicket}-{p.priority}</span>
                    <span>{today}</span>
                  </div>
                  <span className="label">Pay to the order of</span>
                  <div className="cheque-line">
                    <span className="payee">{p.payee}</span>
                    <span className="amt-box mono">{money(p.amount)}</span>
                  </div>
                  <p className="words">{chequeWords(p.amount)} dollars</p>
                  <p className="memo"><span className="label">Memo</span> {toolLabel(p.kind)}{p.ref_id ? ` #${p.ref_id}` : ''} · for #{(p.unblocks_tickets.length ? p.unblocks_tickets : [p.fromTicket]).join(', #')}{p.due_date ? ` · due ${p.due_date}` : ''}</p>
                  <p className="reason">{p.reason}</p>
                  {done ? (
                    <div className="cheque-foot">
                      <span className="signed">{done.by}</span>
                      <span className="paid-stamp">Paid · #{done.id}</span>
                    </div>
                  ) : (
                    <div className="cheque-foot">
                      {short ? <span className="warn">More than checking holds</span> : <span className="sig-line">{signer || ' '}</span>}
                      <button className="btn primary" disabled={!signer.trim() || paying !== null || running !== null} onClick={() => approve(p)}>
                        {paying === key ? 'Signing…' : 'Approve & sign'}
                      </button>
                    </div>
                  )}
                </article>
              )
            })}
          </div>
        </aside>
      </main>

      {toast && <div className={`toast ${toast.tone}`} role="status">{toast.text}</div>}
    </div>
  )
}

function crewLine(e: AgentEvent | undefined, state: string): string {
  if (!e) return 'On shift'
  if (e.kind === 'final_output') return 'Report filed'
  if (state === 'done') return 'Off the clock'
  const call = e.tool_calls.find((c) => c.tool !== 'final_result')
  if (call?.tool.startsWith('ask_')) return `Asking ${AGENTS[call.tool.slice(4) as AgentName]?.name ?? call.tool.slice(4)}`
  if (call) return toolLabel(call.tool)
  if (e.kind === 'start') return 'Picked it up'
  if (e.kind === 'error') return 'Hit a snag'
  return 'Thinking…'
}

function TeeOnPress() {
  return (
    <svg className="tee" viewBox="0 0 120 80" aria-hidden>
      <rect x="6" y="58" width="108" height="10" rx="2" />
      <path d="M38 14 L50 8 Q60 16 70 8 L82 14 L94 26 L84 34 L80 30 L80 56 L40 56 L40 30 L36 34 L26 26 Z" />
      <path d="M20 4 H100" strokeDasharray="4 4" />
    </svg>
  )
}
