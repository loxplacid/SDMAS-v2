"""Deterministic process-mining foundation (TASK 19).

Reads from existing persisted event sources — ``approval_history`` +
``workflow_instances``, ``case_events`` + ``cases``,
``system_exception_events`` + ``system_exceptions`` — and projects
process-mining metrics without any external platform dependency.

Capabilities
------------
- **Process discovery** — reconstruct the actual process model from event logs
- **Case identification** — group events into distinct process instances
- **Process variants** — find distinct execution paths through the process
- **Cycle time** — measure wait times and total case duration
- **Bottlenecks** — identify steps with longest waiting times
- **Rework** — detect repeated steps in a case's lifecycle
- **SLA violations** — detect cases that exceeded time limits
- **Transition frequency** — how often each state-to-state transition occurs

All analysis is deterministic — no AI narratives, no external LLM calls.
"""
