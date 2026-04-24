# Round 2 Problem Statement (Extended from Round 1)

## Title
Multi-Agent Enterprise Report Orchestration with Timezone-Aware Delivery, Retry Policy, and Failure Escalation

## One-line Summary
We extend `daily_report_env` into a realistic enterprise workflow environment where multiple agents must generate the correct report format (PDF/Excel), deliver it to the correct customer at the correct timezone window, track state in a live database, and handle failures with retry and escalation policies.

## Why this matters
Real business reporting is not a single-step generation task. It is a long-horizon, partially observable process with changing failures, delivery risks, and strict SLAs:
- wrong-customer delivery risk
- timezone scheduling errors
- transient and permanent infrastructure failures (for example, LAN failure)
- delayed success signals after multi-step execution

This environment trains LLM agents to reason over state transitions and policy constraints instead of shortcutting to a static output.

## Theme Alignment
- **Primary:** Theme #3.1 World Modeling (Professional Tasks)
- **Secondary:** Theme #1 Multi-Agent Interactions
- **Secondary:** Theme #2 Long-Horizon Planning and Instruction Following

## Environment Concept
The environment simulates a daily reporting operation with:
- multiple report types (`daily_header`, `daily_summary`, `daily_full`, plus extended customer report jobs)
- multiple output formats (PDF and Excel)
- a customer routing layer (report must go to the assigned customer)
- timezone-aware scheduling windows
- live DB status updates for each report attempt
- retry policy (`max_retries=5`)
- auto escalation email after final failure

## Agents and Responsibilities
- **PlannerAgent**: selects jobs by timezone and SLA window.
- **GeneratorAgent**: generates report artifacts (PDF/Excel).
- **ValidationAgent**: verifies content, format, and customer routing correctness.
- **RetryAgent**: decides retry attempts and records attempt counts.
- **NotificationAgent**: sends success/failure/escalation emails.
- **OversightAgent** (bonus): monitors the full trace and explains policy violations.

## Partial Observability
Agents do not see complete root cause directly. They observe:
- current DB status + attempt count
- last action result
- time and timezone context
- delivery and email outcomes

Root causes (network outage, schema mismatch, invalid mapping) can be hidden and inferred from outcomes.

## Success Criteria
An episode is successful only if the agent stack:
1. Generates the required report format correctly.
2. Delivers to the correct customer.
3. Updates DB lifecycle states correctly (`started` -> `in_progress` -> terminal state).
4. Respects retry policy (up to 5 tries).
5. Sends escalation email on terminal failure.
6. Meets timezone/SLA timing constraints.

## Round 2 Novelty vs Round 1
Round 1 baseline: static single-report PDF generation.  
Round 2 extension:
- dynamic multi-customer, multi-timezone scheduling
- dual-format output (PDF + Excel)
- policy-constrained failure handling and escalation
- multi-agent coordination and oversight
- measurable long-horizon reward improvement

## Expected Demonstration
- before/after training behavior and reward curves
- scenario demos (normal, transient failure, permanent LAN failure)
- trace view of actions, DB updates, retries, and email events
- OpenEnv-compatible episode interaction and reproducible metrics
