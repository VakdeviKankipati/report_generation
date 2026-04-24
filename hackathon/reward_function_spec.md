# Reward Function Specification (Round 2 Extension)

## Goal
Reward complete and policy-correct enterprise workflow behavior, not just artifact generation.

## Event Rewards (per step)

| Event | Reward |
|---|---:|
| Correct report artifact generated (PDF or Excel required by task) | +5.0 |
| Correct customer routing confirmed | +8.0 |
| Correct DB status transition for current step | +3.0 |
| SLA/timezone window satisfied | +2.0 |
| Correct escalation email sent after terminal failure | +4.0 |
| Correct root-cause tag in failure email | +2.0 |
| Wrong customer delivery | -10.0 |
| Missing/invalid DB state transition | -6.0 |
| Retry when not needed | -2.0 |
| No escalation after 5 failed attempts | -8.0 |
| Invalid action/schema/tool call | -3.0 |

## Terminal Rewards
- **Episode success bonus:** `+10.0` when all policy checks pass.
- **Terminal failure penalty:** `-6.0` if job remains unresolved after max retries and escalation policy is violated.

## Retry Logic
- `max_retries = 5`
- Retries `1-4` are allowed when failures are transient.
- At retry `5`, the agent must either:
  - recover and mark `success`, or
  - mark `failed`, send escalation email, and persist final DB state.

## Suggested Reward Formula

Let:
- `r_event_t` be sum of event rewards at step `t`
- `r_policy_t` be policy penalties at step `t`
- `r_terminal` be terminal bonus/penalty when done

Then:

`R_total = sum_t (r_event_t + r_policy_t) + r_terminal`

Optional normalization for model stability:

`R_norm = clip((R_total - R_min) / (R_max - R_min), 0.01, 0.99)`

## Metrics to Report in Demo
- end-to-end success rate
- wrong-customer delivery rate
- average retries per job
- escalation compliance rate
- SLA compliance rate
- mean return and reward trend over training

## Anti-Goodhart Guards
- require consistency across DB state and email state (not one alone)
- assign strongest negative reward to wrong-customer delivery
- penalize unnecessary retries to avoid reward farming
- gate terminal success bonus on all critical policy checks

## Example Scenarios
1. **Happy path**: success on first attempt, all statuses valid.
2. **Transient fail**: fails twice, succeeds on third attempt, no escalation email.
3. **Permanent LAN fail**: fails all 5 attempts, sends escalation email, final DB state `failed`.
4. **Policy violation**: report failed 5 times but no escalation email (heavy penalty).
