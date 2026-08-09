import { cn, capitalize, formatDateTime } from '../../lib/utils'
import { Badge } from '../ui/badge'

// ── Types ──

export interface WorkflowStepView {
  id: number
  name: string
  label: string | null
  step_order: number
  is_initial: boolean
  is_final: boolean
  assigned_role: string | null
}

export interface WorkflowHistoryView {
  id: number
  action: string
  actor_id: number | null
  comment: string | null
  created_at: string
}

export interface WorkflowStatusInstance {
  id: number
  status: string
  current_step_id: number
  entity_type: string
  entity_id: number
  created_by: number | null
  created_at: string
  workflow: {
    id: number
    name: string
    code: string
    steps?: WorkflowStepView[]
  } | null
  history: WorkflowHistoryView[]
}

export interface WorkflowStatusTransition {
  label: string | null
  to_step_id: number
  to_step_name: string
  required_role: string | null
}

interface WorkflowStatusProps {
  instance: WorkflowStatusInstance
  /** Transitions the current actor may take (already role-filtered server-side). */
  availableTransitions?: WorkflowStatusTransition[]
  className?: string
  /** Compact mode: no history timeline, just the stepper. */
  compact?: boolean
}

// ── Labels ──

const STATUS_LABELS: Record<string, string> = {
  active: 'Pending',
  completed: 'Approved',
  cancelled: 'Cancelled',
}

const STATUS_VARIANT: Record<string, 'info' | 'success' | 'danger' | 'warning' | 'neutral'> = {
  active: 'info',
  completed: 'success',
  cancelled: 'danger',
}

const ACTION_VARIANT: Record<string, 'success' | 'danger' | 'warning' | 'info' | 'neutral'> = {
  submit: 'info',
  approve: 'success',
  reject: 'danger',
  return: 'warning',
  cancel: 'neutral',
}

function getActorLabel(entry: WorkflowHistoryView): string {
  return entry.actor_id ? `User #${entry.actor_id}` : 'System'
}

/**
 * Reusable workflow progress display (P14 §6): current step, completed
 * steps, pending action, responsible role, and the immutable history
 * timeline.  Rendered from the *real* workflow definition + instance —
 * never a hardcoded pipeline.
 *
 * The stepper derives state from the instance alone:
 * - steps with `step_order < current` → completed
 * - `step_order === current`      → in progress (pending action shown)
 * - `step_order > current`        → pending
 *
 * Terminal instances (completed / cancelled) mark every step resolved.
 */
export function WorkflowStatus({
  instance,
  availableTransitions = [],
  className,
  compact = false,
}: WorkflowStatusProps) {
  const steps = [...(instance.workflow?.steps || [])].sort(
    (a, b) => a.step_order - b.step_order
  )
  const currentStep = steps.find((s) => s.id === instance.current_step_id)
  const currentOrder = currentStep?.step_order ?? -1
  const isTerminal = instance.status === 'completed' || instance.status === 'cancelled'
  const currentStepMissing = !isTerminal && instance.current_step_id > 0 && !currentStep

  const pendingTransitions = availableTransitions.filter((t) => t.label)
  const pendingActionLabel = pendingTransitions.map((t) => t.label).join(' / ')
  const pendingRole = steps.find((s) => s.id === instance.current_step_id)?.assigned_role

  return (
    <div className={cn('space-y-4', className)}>
      {/* Header: workflow name + status */}
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-[var(--color-text-primary)] truncate">
            {instance.workflow?.name || `Workflow #${instance.workflow?.id ?? ''}`}
          </p>
          {!compact && (
            <p className="text-xs text-[var(--color-text-tertiary)] mt-0.5">
              {instance.entity_type.replace(/_/g, ' ')} #{instance.entity_id}
            </p>
          )}
        </div>
        <Badge variant={STATUS_VARIANT[instance.status] || 'neutral'} size="sm">
          {STATUS_LABELS[instance.status] || capitalize(instance.status)}
        </Badge>
      </div>

      {/* Stepper */}
      {steps.length > 0 ? (
        <ol className="space-y-0" aria-label="Workflow steps">
          {steps.map((step, idx) => {
            const isCurrent = !isTerminal && step.id === instance.current_step_id
            const isCompleted = isTerminal || step.step_order < currentOrder
            return (
              <li key={step.id} className="relative flex items-start gap-3 pb-4 last:pb-0">
                {/* Connector line */}
                {idx < steps.length - 1 && (
                  <span
                    aria-hidden="true"
                    className={cn(
                      'absolute left-[11px] top-6 bottom-0 w-0.5 rounded-full',
                      isCompleted ? 'bg-[var(--color-brand-accent)]' : 'bg-[var(--color-border)]'
                    )}
                  />
                )}
                {/* Node */}
                <span
                  aria-hidden="true"
                  className={cn(
                    'relative z-10 mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full border-2',
                    isCompleted
                      ? 'border-[var(--color-brand-accent)] bg-[var(--color-brand-accent)] text-white'
                      : isCurrent
                        ? 'border-[var(--color-brand-accent)] bg-[var(--color-brand-accent-subtle)] text-[var(--color-brand-accent)]'
                        : 'border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-muted)]'
                  )}
                >
                  {isCompleted ? (
                    <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  ) : isCurrent ? (
                    <span className="h-2 w-2 rounded-full bg-[var(--color-brand-accent)] motion-safe:animate-pulse-soft" />
                  ) : (
                    <span className="text-[10px] font-semibold">{idx + 1}</span>
                  )}
                </span>
                {/* Step content */}
                <div className="min-w-0 flex-1 pt-0.5">
                  <div className="flex items-center gap-2">
                    <p
                      className={cn(
                        'text-sm font-medium truncate',
                        isCompleted || isCurrent
                          ? 'text-[var(--color-text-primary)]'
                          : 'text-[var(--color-text-muted)]'
                      )}
                    >
                      {step.label || capitalize(step.name)}
                    </p>
                    {isCurrent && (
                      <Badge variant="primary" size="sm" className="flex-shrink-0">
                        In progress
                      </Badge>
                    )}
                  </div>
                  {step.assigned_role && (
                    <p className="text-xs text-[var(--color-text-tertiary)] mt-0.5">
                      Responsible: <span className="font-medium text-[var(--color-text-secondary)]">{step.assigned_role}</span>
                    </p>
                  )}
                </div>
              </li>
            )
          })}
        </ol>
      ) : (
        <p className="text-sm text-[var(--color-text-tertiary)] py-2">
          No steps are defined for this workflow.
        </p>
      )}

      {/* Pending action — only for active instances */}
      {instance.status === 'active' && (
        <div className="rounded-lg border border-[var(--color-border-light)] bg-[var(--color-surface-hover)] px-3 py-2.5">
          <p className="text-xs text-[var(--color-text-tertiary)]">Pending action</p>
          <p className="text-sm font-medium text-[var(--color-text-primary)] mt-0.5">
            {pendingActionLabel || 'Awaiting approval'}
            {pendingRole && (
              <span className="text-[var(--color-text-tertiary)] font-normal">
                {' '}· requires <span className="font-medium text-[var(--color-text-secondary)]">{pendingRole}</span>
              </span>
            )}
            {currentStepMissing && (
              <span className="text-[var(--color-text-tertiary)] font-normal">
                {' '}· current step no longer defined in the workflow
              </span>
            )}
          </p>
        </div>
      )}

      {/* History timeline */}
      {!compact && instance.history.length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)] mb-2">
            History ({instance.history.length})
          </p>
          <ol className="relative pl-6 space-y-0">
            <span
              aria-hidden="true"
              className="absolute left-[11px] top-1 bottom-1 w-0.5 bg-[var(--color-border)]"
            />
            {instance.history.map((entry) => (
              <li key={entry.id} className="relative pb-3 last:pb-0">
                <span
                  aria-hidden="true"
                  className={cn(
                    'absolute left-[-17px] top-1.5 h-[10px] w-[10px] rounded-full border-2',
                    entry.action === 'approve'
                      ? 'border-emerald-500 bg-emerald-50 dark:bg-emerald-900/20'
                      : entry.action === 'reject'
                        ? 'border-red-500 bg-red-50 dark:bg-red-900/20'
                        : entry.action === 'cancel'
                          ? 'border-[var(--color-text-muted)] bg-[var(--color-surface)]'
                          : 'border-[var(--color-brand-accent)] bg-[var(--color-brand-accent-subtle)]'
                  )}
                />
                <div className="flex items-center gap-2 flex-wrap">
                  <Badge variant={ACTION_VARIANT[entry.action] || 'neutral'} size="sm">
                    {capitalize(entry.action)}
                  </Badge>
                  <span className="text-[11px] text-[var(--color-text-muted)]">
                    {formatDateTime(entry.created_at)} · {getActorLabel(entry)}
                  </span>
                </div>
                {entry.comment && (
                  <p className="text-xs text-[var(--color-text-secondary)] mt-1 bg-[var(--color-surface)] rounded-md px-2.5 py-1.5 border border-[var(--color-border-light)]">
                    "{entry.comment}"
                  </p>
                )}
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  )
}

export default WorkflowStatus
