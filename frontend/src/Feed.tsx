import { useState } from 'react'
import type { AgentEvent, AgentName } from './api'
import { AGENTS, toolLabel } from './desk'

const agentStyle = (a: AgentName) => ({ '--agent': AGENTS[a].color }) as React.CSSProperties

export function Avatar({ agent, small }: { agent: AgentName; small?: boolean }) {
  return (
    <span className={`avatar ${small ? 'small' : ''}`} style={agentStyle(agent)} aria-hidden>
      {AGENTS[agent].mono}
    </span>
  )
}

const clock = (iso: string) => new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })

function argText(args: unknown): string {
  if (!args) return ''
  if (typeof args === 'string') return args
  return Object.entries(args as Record<string, unknown>)
    .map(([k, v]) => `${k}=${typeof v === 'string' ? JSON.stringify(v.length > 60 ? v.slice(0, 60) + '…' : v) : JSON.stringify(v)}`)
    .join(', ')
}

function ToolRow({ tool, args, agent }: { tool: string; args: unknown; agent: AgentName }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="tool-row" style={agentStyle(agent)}>
      <button className="tool-btn mono" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <span aria-hidden>⚙</span> {tool}(<span className="tool-args">{argText(args)}</span>)
      </button>
      {open && <pre className="tool-detail mono">{JSON.stringify(args, null, 2)}</pre>}
    </div>
  )
}

/** One audit-trail step, drawn on its agent's kind of paper. */
export function FeedItem({ e }: { e: AgentEvent }) {
  if (e.agent === 'human') return null
  const agent = e.agent
  const meta = AGENTS[agent]
  if (!meta) return null
  const calls = e.tool_calls.filter((c) => c.tool !== 'final_result')
  const delegations = calls.filter((c) => c.tool.startsWith('ask_'))
  const tools = calls.filter((c) => !c.tool.startsWith('ask_'))

  if (e.kind === 'model_request') {
    // Tool results coming back to the agent: one quiet line.
    if (!e.tool_results.length || e.tool_results.every((t) => t === 'final_result')) return null
    return (
      <div className="result-line mono" style={agentStyle(agent)}>
        ↩ {meta.name} got back {e.tool_results.filter((t) => t !== 'final_result').map(toolLabel).join(', ')}
      </div>
    )
  }

  const head = (label: string) => (
    <header className="msg-head">
      <Avatar agent={agent} small />
      <span className="msg-name">{meta.name}</span>
      <span className="msg-label">{label}</span>
      <time className="mono">{clock(e.time)}</time>
    </header>
  )

  if (e.kind === 'start') {
    const from = Array.isArray(e.chain) && e.chain.length > 1 ? e.chain[e.chain.length - 2] : null
    if (from) return null // the delegation slip already shows this hand-off
    return (
      <div className="clock-in" style={agentStyle(agent)}>
        <Avatar agent={agent} small /> {meta.name} clocked in · <time className="mono">{clock(e.time)}</time>
      </div>
    )
  }

  if (e.kind === 'final_output') {
    return (
      <article className={`msg paper-${meta.style} filed`} style={agentStyle(agent)}>
        {head('report filed')}
        <p>{e.said}</p>
      </article>
    )
  }

  if (e.kind === 'error') {
    return (
      <article className="msg error" style={agentStyle(agent)}>
        {head('hit a snag')}
        <p>{e.said}</p>
      </article>
    )
  }

  const said = e.said?.trim()
  return (
    <>
      {said && (
        <article className={`msg paper-${meta.style}`} style={agentStyle(agent)}>
          {head(LABEL[meta.style])}
          <p>{said}</p>
        </article>
      )}
      {tools.map((c, i) => (
        <ToolRow key={i} tool={c.tool} args={c.args} agent={agent} />
      ))}
      {delegations.map((c, i) => {
        const to = c.tool.slice(4) as AgentName
        const req = typeof c.args === 'object' && c.args ? String((c.args as Record<string, unknown>).request ?? '') : ''
        return (
          <div key={'d' + i} className="route-slip">
            <div className="route-line">
              <Avatar agent={agent} small />
              <span className="route-arrow" aria-hidden />
              <Avatar agent={to} small />
              <span className="route-to">
                {meta.name} → {AGENTS[to]?.name ?? to}
              </span>
              <time className="mono">{clock(e.time)}</time>
            </div>
            {req && <p className="route-req">“{req}”</p>}
          </div>
        )
      })}
    </>
  )
}

const LABEL = { memo: 'memo', tag: 'stock note', ledger: 'ledger note', slip: 'work slip', speech: 'says' }
