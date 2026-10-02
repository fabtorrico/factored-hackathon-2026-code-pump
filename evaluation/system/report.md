# Phase 6 system evaluation report

Generated: 2026-10-02T22:17:18+00:00

Prototype safety and robustness evidence, not production assurance. Every case runs against the real application in-process.

**Totals:** 125 cases - 125 PASS, 0 FAIL, 0 SKIP.

## Scorecard

| Category | Cases | Pass | Fail | Skip |
| --- | ---: | ---: | ---: | ---: |
| A. Authentication | 9 | 9 | 0 | 0 |
| B. Authorization | 8 | 8 | 0 | 0 |
| C. Agent boundary | 6 | 6 | 0 | 0 |
| D. Incident contract | 7 | 7 | 0 | 0 |
| E. Identification | 6 | 6 | 0 | 0 |
| F. Policy matrix | 17 | 17 | 0 | 0 |
| G. Grounding | 6 | 6 | 0 | 0 |
| H. Missing evidence | 3 | 3 | 0 | 0 |
| I. Tool failure | 5 | 5 | 0 | 0 |
| J. Act->Verify | 5 | 5 | 0 | 0 |
| K. Persistence | 5 | 5 | 0 | 0 |
| L. Handoff | 5 | 5 | 0 | 0 |
| M. Audit | 5 | 5 | 0 | 0 |
| N. PII safety | 5 | 5 | 0 | 0 |
| O. API robustness | 6 | 6 | 0 | 0 |
| P. Frontend contract | 5 | 5 | 0 | 0 |
| Q. AI status | 3 | 3 | 0 | 0 |
| R. Adversarial | 4 | 4 | 0 | 0 |
| S. Concurrency | 4 | 4 | 0 | 0 |
| E2E. Live curated | 8 | 8 | 0 | 0 |
| PERF. Latency | 3 | 3 | 0 | 0 |

## Latency (local, small sample, not an SLA)

| Operation | Iterations | p50 (ms) | p95 (ms) |
| --- | ---: | ---: | ---: |
| declined_resolution | 25 | 37.192 | 46.963 |
| pending_escalation | 25 | 56.792 | 111.763 |
| agent_case_detail | 25 | 3.911 | 4.218 |

## Failures

None.

## Cases

### A. Authentication

- `PASS` **A01** Read customer context with no session - no-session read refused with invalid_session
- `PASS` **A02** Read with an unknown session id - unknown session refused with invalid_session
- `PASS` **A03** Read with an expired session - expired session refused with expired_session
- `PASS` **A04** Read with a blank session header - blank session header is refused rather than treated as self
- `PASS` **A05** Session id echoed in a response - session identifier absent from customer responses
- `PASS` **A06** Incident submitted with no session - invalid session abstains and creates no case
- `PASS` **A07** Incident submitted with an expired session - expired session is indistinguishable from invalid at policy level
- `PASS` **A08** Customer session used as agent credential - a customer session cannot authorize an agent read
- `PASS` **A09** Expired agent session - expired agent session refused
### B. Authorization

- `PASS` **B01** Customer lists own transactions - an authenticated customer sees only its own transactions
- `PASS` **B02** Customer widens scope to another customer - a session cannot widen a read to another customer
- `PASS` **B03** Customer reads another customer's transaction - another customer's transaction is reported as transaction_not_found
- `PASS` **B04** Foreign vs absent transaction - absent and foreign transactions share one indistinguishable answer
- `PASS` **B05** Candidate search with a foreign scope - candidate search is session-scoped and refuses a foreign scope
- `PASS` **B06** Incident on another customer's transaction - another customer's transaction yields a no-match clarification, not a leak
- `PASS` **B07** Read another customer's incident timeline - a foreign incident timeline is indistinguishable from a missing one
- `PASS` **B08** Query parameter on the self-context route - the self-context route accepts no query parameters at all
### C. Agent boundary

- `PASS` **C01** Agent queue with no credential - agent queue refuses an absent credential
- `PASS` **C02** Agent credential used as a customer session - an agent credential cannot read banking data as a customer
- `PASS` **C03** POST to an agent case - POST on an agent case is not allowed (read-only)
- `PASS` **C04** PUT to an agent case - PUT on an agent case is not allowed (read-only)
- `PASS` **C05** Agent queue identity exposure - agent queue carries no customer identity
- `PASS` **C06** Agent detail identity exposure - agent detail carries no customer identity
### D. Incident contract

- `PASS` **D01** Both identification modes supplied - exactly one of transaction_id / filters is required
- `PASS` **D02** Unknown top-level field - prose or unknown top-level fields are rejected, so no free text reaches the workflow
- `PASS` **D03** Loosely typed boolean - a loosely typed boolean is rejected (strict model)
- `PASS` **D04** Blank transaction reference - a blank transaction reference is rejected before any lookup
- `PASS` **D05** Out-of-domain filter value - an out-of-domain filter value is refused rather than silently dropped
- `PASS` **D06** Unknown filter key - an unknown filter key is rejected instead of being silently ignored
- `PASS` **D07** Non-numeric amount bound - a non-numeric amount bound is refused before a search runs
### E. Identification

- `PASS` **E01** Exact declined transaction - an exact declined transaction resolves at status level
- `PASS` **E02** Two owning candidates - two owned candidates produce a clarification with both options
- `PASS` **E03** No owning match - a search with no owned match clarifies with an empty candidate list
- `PASS` **E04** Search never crosses customers - candidate search never returns another customer's rows
- `PASS` **E05** Verified but unsupported status - a verified but unsupported status escalates rather than being remapped
- `PASS` **E06** Candidates carry identity - clarification candidates carry no customer identity
### F. Policy matrix

- `PASS` **F01** Precedence: invalid session over status - {'session_valid': False, 'candidate_transaction_count': 1, 'transaction_status': 'Declined'} -> ABSTAIN/invalid_session
- `PASS` **F02** Precedence: unauthorized over status - {'authorized': False, 'candidate_transaction_count': 1, 'transaction_status': 'Declined'} -> ABSTAIN/unauthorized
- `PASS` **F03** Out of scope over no candidates - {'in_scope': False, 'candidate_transaction_count': 0} -> ABSTAIN/out_of_scope
- `PASS` **F04** Tool failure over identification - {'tool_failure_exhausted': True, 'candidate_transaction_count': 0} -> ESCALATE/tool_failure_exhausted
- `PASS` **F05** Evidence missing over identification - {'required_evidence_missing': True, 'candidate_transaction_count': 2} -> ESCALATE/required_evidence_missing
- `PASS` **F06** Zero candidates - {'candidate_transaction_count': 0} -> CLARIFY/no_matching_transaction
- `PASS` **F07** Multiple candidates over status - {'candidate_transaction_count': 2, 'transaction_status': 'Pending'} -> CLARIFY/multiple_candidate_transactions
- `PASS` **F08** Declined - {'candidate_transaction_count': 1, 'transaction_status': 'Declined'} -> RESOLVE/declined_status
- `PASS` **F09** Pending - {'candidate_transaction_count': 1, 'transaction_status': 'Pending'} -> ESCALATE/pending_status
- `PASS` **F10** Reversed - {'candidate_transaction_count': 1, 'transaction_status': 'Reversed'} -> ESCALATE/reversed_status
- `PASS` **F11** Approved with unresolved issue - {'candidate_transaction_count': 1, 'transaction_status': 'Approved', 'approved_with_unresolved_issue': True} -> ESCALATE/approved_unresolved_issue
- `PASS` **F12** Approved without incident - {'candidate_transaction_count': 1, 'transaction_status': 'Approved'} -> ABSTAIN/approved_no_supported_incident
- `PASS` **F13** Unknown status - {'candidate_transaction_count': 1, 'transaction_status': 'Processing'} -> ESCALATE/unknown_transaction_status
- `PASS` **F14** Blank status - {'candidate_transaction_count': 1, 'transaction_status': '   '} -> ESCALATE/unknown_transaction_status
- `PASS` **F15** Status whitespace - {'candidate_transaction_count': 1, 'transaction_status': '  Declined  '} -> RESOLVE/declined_status
- `PASS` **F16** Determinism - 100 identical evaluations produced one identical decision
- `PASS` **F17** Version pinning - the policy version is pinned to 1.0.0
### G. Grounding

- `PASS` **G01** Declined resolution wording - a declined resolution carries status and verbatim code only, no cause
- `PASS` **G02** RESOLVE action scope - RESOLVE performs no operational action and asserts no money movement
- `PASS` **G03** Workflow result schema - the workflow result has no free-text field a model could fill
- `PASS` **G04** Reversed wording - a reversed transaction never claims the funds were returned
- `PASS` **G05** Pending wording - a pending transaction records that settlement is unknown
- `PASS` **G06** Handoff evidence - handoff evidence values are the curated values verbatim
### H. Missing evidence

- `PASS` **H01** Absent curated values - absent curated values read back as absent, never fabricated
- `PASS` **H02** Handoff omits absent evidence - the handoff omits evidence the curated row does not carry
- `PASS` **H03** Agent movement source - the agent movement summary is built from the persisted handoff only
### I. Tool failure

- `PASS` **I01** Curated database missing - a missing curated database is a 503 data_unavailable, not a crash
- `PASS` **I02** Workflow with unavailable lookup - an exhausted banking lookup escalates with no fabricated transaction facts
- `PASS` **I03** Support-case write fails - a support-case write failure is reported, never disguised as an escalation
- `PASS` **I04** Handoff write fails - an unverifiable handoff write fails the escalation
- `PASS` **I05** Handoff read back fails - a handoff that cannot be read back fails the escalation
### J. Act->Verify

- `PASS` **J01** Escalation implies persisted case - a completed escalation always has a persisted support case
- `PASS` **J02** Escalation implies persisted handoff - a completed escalation always has a persisted handoff a human can read
- `PASS` **J03** Unverified escalation leaves no case - an escalation that cannot be verified leaves no case behind
- `PASS` **J04** Recorded action order - the recorded action order is attempted -> created -> verified -> escalated
- `PASS` **J05** Failed write recorded - an unverified write records both verification_failed and workflow_failed
### K. Persistence

- `PASS` **K01** Reopen the operational store - a reopened store reads the same case and handoff
- `PASS` **K02** Incident terminal status survives reopen - an incident survives a reopen with its terminal status
- `PASS` **K03** Events survive reopen - workflow events survive a reopen in order
- `PASS` **K04** Schema initialization is idempotent - schema initialization is idempotent and non-destructive
- `PASS` **K05** Legacy database gains handoffs - an already-initialized database gains the handoffs table without an ALTER
### L. Handoff

- `PASS` **L01** Request restated - the handoff restates the submitted request faithfully
- `PASS` **L02** Search-based request - a search-based escalation records the filters that were used
- `PASS` **L03** Verified facts present - the handoff records the verified ownership and status facts
- `PASS` **L04** Actions complete - the handoff records both the case write and its verification
- `PASS` **L05** Route and policy - the handoff carries the same pinned decision and a safe route
### M. Audit

- `PASS` **M01** One audit event per tool call - each banking tool call records exactly one audit event
- `PASS` **M02** Denied read audited - a denied read is audited with its outcome and reason
- `PASS` **M03** Audit hides the credential - audit events carry a fingerprint, never the session identifier
- `PASS` **M04** Audit limit validation - the audit limit is bounded and validated
- `PASS` **M05** Incident created before policy - an incident is recorded before policy is evaluated
### N. PII safety

- `PASS` **N01** Curated tables drop PII columns - raw PII columns never reach the curated DuckDB tables
- `PASS` **N02** Customer responses PII-free - customer responses contain no contact or identity attributes
- `PASS` **N03** Product source has no customer ids - no curated customer identifier appears in product source
- `PASS` **N04** Env and data ignored - the data tree and the local environment file are ignored
- `PASS` **N05** Committed env example - the committed environment example carries no secret
### O. API robustness

- `PASS` **O01** Unknown path - an unknown path is a clean 404
- `PASS` **O02** Wrong method - an unsupported method is a 405
- `PASS` **O03** Malformed JSON - a malformed body is rejected before the workflow runs
- `PASS` **O04** Unsupported query parameter - an unsupported query parameter is refused, not ignored
- `PASS` **O05** Health endpoint - the health endpoint is available
- `PASS` **O06** Empty incident body - an empty incident body is rejected
### P. Frontend contract

- `PASS` **P01** Customer copy hides policy internals - customer copy exposes no policy rule identifier
- `PASS` **P02** Agent client is read-only - the agent API client exposes only session, list and detail reads
- `PASS` **P03** Credentials in headers only - the two credentials travel in distinct headers and never in bodies
- `PASS` **P04** No credential persistence - no frontend code persists credentials to web storage
- `PASS` **P05** Outcome labels safe - agent outcome labels make no unsupported money claim
### Q. AI status

- `PASS` **Q01** No runtime LLM - the runtime makes no LLM call
- `PASS` **Q02** LLM benchmark status - the LLM benchmark harness documents that it was not executed
- `PASS` **Q03** Baseline documented - the Phase 4A baseline evaluation is documented and reproducible
### R. Adversarial

- `PASS` **R01** Instruction-like prose - instruction-like prose is not a field, so it cannot reach the workflow
- `PASS` **R02** Policy override fields - no caller can submit a status, outcome, rule or identity
- `PASS` **R03** SQL-like transaction reference - a SQL-like reference is treated as an opaque id and changes nothing
- `PASS` **R04** Unicode instruction-like reference - unicode instruction-like text is treated as a plain unmatched reference
### S. Concurrency

- `PASS` **S01** Same movement escalated twice - two escalations of the same movement are two distinct cases
- `PASS` **S02** Four concurrent escalations - four concurrent escalations each produced a unique, persisted case
- `PASS` **S03** Repeated agent reads - repeated agent reads are stable
- `PASS` **S04** Session id uniqueness - 20 issued sessions produced 20 distinct identifiers
### E2E. Live curated

- `PASS` **E2E-1** Declined demo movement - live declined movement resolved to RESOLVE/F_DECLINED
- `PASS` **E2E-2** Pending demo movement - live pending movement resolved to ESCALATE/G_PENDING
- `PASS` **E2E-3** Reversed demo movement - live reversed movement resolved to ESCALATE/H_REVERSED
- `PASS` **E2E-4** Approved with reported issue - a live approved movement with a reported issue escalates
- `PASS` **E2E-5** Ambiguous demo reference - a live ambiguous reference clarified over 2 candidates
- `PASS` **E2E-6** Search with no match - a live search with no match clarifies with an empty list
- `PASS` **E2E-7** Out-of-scope live request - an out-of-scope live request abstains and acts on nothing
- `PASS` **E2E-8** Escalation visible to the agent - a live escalation is visible to the agent with its handoff and timeline
### PERF. Latency

- `PASS` **PERF-1** Declined resolution latency - declined resolution p50=37.192ms p95=46.963ms (n=25)
- `PASS` **PERF-2** Pending escalation latency - pending escalation p50=56.792ms p95=111.763ms (n=25)
- `PASS` **PERF-3** Agent case detail latency - agent case detail p50=3.911ms p95=4.218ms (n=25)

