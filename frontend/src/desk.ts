import type { AgentName } from './api'

export interface AgentMeta {
  name: string
  mono: string
  color: string
  role: string
  style: 'memo' | 'tag' | 'ledger' | 'slip' | 'speech'
}

// Each agent has its own colour, monogram and "paper" in the feed (see output/design.md).
export const AGENTS: Record<AgentName, AgentMeta> = {
  boss: { name: 'Boss', mono: 'B', color: 'var(--a-boss)', role: 'Reads the ticket, routes the work', style: 'memo' },
  inventory: { name: 'Inventory', mono: 'IN', color: 'var(--a-inventory)', role: 'Counts stock by SKU and size', style: 'tag' },
  accounting: { name: 'Accounting', mono: 'AC', color: 'var(--a-accounting)', role: 'Cash, invoices, margins', style: 'ledger' },
  facilities: { name: 'Facilities', mono: 'FA', color: 'var(--a-facilities)', role: 'Lease, rent, the building', style: 'slip' },
  customer_service: { name: 'Customer Service', mono: 'CS', color: 'var(--a-service)', role: 'Talks to students and clubs', style: 'speech' },
}

export const AGENT_ORDER: AgentName[] = ['boss', 'inventory', 'accounting', 'facilities', 'customer_service']

export const TICKET_KIND: Record<string, string> = {
  customer_order: 'Customer order',
  rent_notice: 'Rent notice',
  price_override: 'Price override',
}

const fmt = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })
export const money = (n: number) => fmt.format(n)

const ONES = ['', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve',
  'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen']
const TENS = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety']
function under1000(n: number): string {
  const h = Math.floor(n / 100)
  const r = n % 100
  const rest = r < 20 ? ONES[r] : TENS[Math.floor(r / 10)] + (r % 10 ? '-' + ONES[r % 10] : '')
  return [h ? ONES[h] + ' hundred' : '', rest].filter(Boolean).join(' ')
}
/** "Two thousand four hundred and 00/100" — the words line on a cheque. */
export function chequeWords(amount: number): string {
  const dollars = Math.floor(amount)
  const cents = Math.round((amount - dollars) * 100)
  const th = Math.floor(dollars / 1000)
  const words = [th ? under1000(th) + ' thousand' : '', under1000(dollars % 1000)].filter(Boolean).join(' ') || 'zero'
  return `${words[0].toUpperCase()}${words.slice(1)} and ${String(cents).padStart(2, '0')}/100`
}

/** "2026-08-31" -> "08.31" for the rubber stamp. */
export const stampDate = (iso: string) => (iso ? iso.slice(5).replace('-', '.') : '')

export const toolLabel = (tool: string) => tool.replaceAll('_', ' ')
