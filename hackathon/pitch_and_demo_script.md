# 3-Min Pitch + 2-Min Demo Script

## 3-Minute Pitch Script

### 0:00 - 0:35 Problem
Today, enterprise reporting is not just generating a file. Teams must generate the right report, in the right format, for the right customer, at the right time zone, with strict tracking and escalation policies. Static report tasks miss this operational complexity.

### 0:35 - 1:20 Our Environment
We extended our Round 1 `daily_report_env` into a multi-agent enterprise workflow environment.  
Agents coordinate across planning, generation, validation, retry logic, notifications, and oversight.  
The world is partially observable: agents only see system outcomes and DB traces, not full root cause.  
We model realistic failures including transient errors and permanent LAN failure for specific customers.

### 1:20 - 2:10 Reward and Training
We use policy-aware reward shaping:
- positive rewards for correct generation, routing, DB transitions, SLA compliance
- penalties for wrong-customer delivery, missing DB updates, unnecessary retries
- mandatory escalation after 5 failed attempts

Training is run using OpenEnv plus a minimal TRL/Unsloth pipeline.  
We show before/after behavior and reward curves demonstrating improved success, fewer policy violations, and better failure handling.

### 2:10 - 3:00 Results and Why It Matters
Our environment captures long-horizon enterprise behavior that generic benchmarks miss:
- multi-step delayed outcomes
- multi-agent interaction
- compliance-style policy checks
- realistic operational traces

This directly improves LLM reliability for real business automation, not just toy tasks.

## 2-Minute Demo Flow

### Demo Scenario A: Happy Path (40 sec)
1. Reset environment with a valid job in active SLA window.
2. Show agent steps: started -> in_progress -> success.
3. Show generated PDF/Excel and correct customer delivery.
4. Show DB row updates and final success status.

### Demo Scenario B: Transient Failure Recovery (40 sec)
1. Inject transient timeout for first two attempts.
2. Show retry counts increment in DB.
3. Third attempt succeeds.
4. Confirm no escalation email is sent when final status is success.

### Demo Scenario C: Permanent LAN Failure (40 sec)
1. Inject permanent LAN failure for one customer.
2. Show five failed attempts.
3. Show escalation email trigger and DB email_sent flag.
4. Final state is failed, policy-compliant.

## Q&A Ready Answers
- **How is this multi-agent?**  
  Distinct agents own planning, generation, validation, retry policy, notifications, and oversight.
- **How is this long-horizon?**  
  Reward depends on end-to-end completion after retries, delivery checks, and escalation.
- **How is reward robust?**  
  It combines artifact quality, routing correctness, state transition correctness, and policy compliance.
- **How is it realistic?**  
  We model enterprise timing, failure patterns, and audit-like DB traces.
