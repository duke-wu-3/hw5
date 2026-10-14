// Thin client for the FastAPI backend from Problem 7 (backend/main.py).
export const API = 'http://localhost:8000'

export type AgentName = 'boss' | 'inventory' | 'accounting' | 'facilities' | 'customer_service'

export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  status: string
  notes: string | null
  created_at: string
  state: 'open' | 'resolved'
}

export interface AgentEvent {
  index: number
  time: string
  run_id: string | null
  agent: AgentName | 'human'
  chain: string[] | string | null
  kind: string
  said: string | null
  tool_calls: { tool: string; args: Record<string, unknown> | string | null }[]
  tool_results: string[]
}

export interface PaymentRequest {
  kind: 'invoice' | 'rent' | 'purchase_order'
  ref_id: number | null
  payee: string
  amount: number
  due_date: string | null
  reason: string
  priority: number
  unblocks_tickets: number[]
}

export interface RateApproval {
  ticket_id: number
  sku: string
  qty: number
  discount_pct: number
  unit_price: number
  order_margin: number
  reason: string
}

export interface TicketOutcome {
  ticket_id: number
  owner: AgentName
  status: string
  decision: string
  customer_message: string | null
  next_steps: string[]
}

export interface TeamReport {
  run_summary: string
  tickets: TicketOutcome[]
  payment_queue: PaymentRequest[]
  rate_approvals?: RateApproval[]
  cash_on_hand: number
  cash_after_payment_queue: number
  deferred: string[]
  risks: string[]
}

export interface RunResult {
  run_id: string
  ticket_id: number
  model: string
  status: string
  report: TeamReport
}

export interface Cash {
  name: string
  balance: number
  date: string
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(API + path, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  tickets: () => call<{ date_today: string; tickets: Ticket[] }>('/tickets'),
  cash: () => call<Cash>('/cash'),
  events: (after: number, limit = 400) =>
    call<{ total: number; events: AgentEvent[] }>(`/events?after=${after}&limit=${limit}`),
  run: (ticketId: number) => call<RunResult>(`/tickets/${ticketId}/run`, { method: 'POST' }),
  approve: (p: PaymentRequest, approvedBy: string) =>
    call<{ payment_id: number; effect: string; balance_before: number; balance_after: number }>(
      '/payments/approve',
      {
        method: 'POST',
        body: JSON.stringify({
          kind: p.kind,
          ref_id: p.ref_id,
          payee: p.payee,
          amount: p.amount,
          approved_by: approvedBy,
          unblocks_tickets: p.unblocks_tickets,
        }),
      },
    ),
  approveRate: (r: RateApproval, approvedBy: string) =>
    call<{ effect: string; unit_price: number; order_total: number; order_margin: number }>('/pricing/approve', {
      method: 'POST',
      body: JSON.stringify({ ticket_id: r.ticket_id, sku: r.sku, qty: r.qty, discount_pct: r.discount_pct, approved_by: approvedBy }),
    }),
  reset: () => call<{ reset: boolean }>('/reset', { method: 'POST' }),
}
