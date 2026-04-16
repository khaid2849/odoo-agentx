# Code Review Report — ODO-24: Access Control & Security

**Date:** 2026-04-16
**Reviewer:** Reviewer Agent (ODO Agent Pipeline)
**PR:** https://github.com/khaid2849/odoo-agentx/pull/8
**Branch:** `feature/odo-14.10`
**Decision:** **NEEDS REVISION** — 4 Blocking CRs open

---

## Overall Decision

**NEEDS REVISION**

Four blocking findings prevent merge. Three are security over-grants (Users receiving write access on models where they should be read-only per spec), and one is missing test coverage for all security-critical paths. Non-blocking findings document scope deviations and design inconsistencies that require PM acknowledgment.

---

## Scope of Review

This PR implements Sub-Goal 5 security work for `agentx_project_management` including:
- 4 security groups (`viewer`, `user`, `manager`, `admin`)
- 44 ACL rows covering 11 models × 4 groups
- 2 record rules (project access, task write restriction)
- Full module scaffold (31 files, 4201 additions)

Review focused on `security/security.xml`, `security/ir.model.access.csv`, record rule domain validity, and cross-file consistency checks.

---

## Blocking Findings

### CR-1 [Blocking]
- **File:** `security/ir.model.access.csv`
- **Line:** Row `access_agentx_customer_request_user`
- **Dimension:** Security — ACL
- **Problem:** User group has `perm_write=1` for `agentx.customer.request`. Spec states "Team Member: CR customer.request" (Create + Read only). Write/Update is not authorized for this group on this model. This allows team members to modify customer requests created by others.
- **Source reference:** ODO-24 task description — "Team Member: CR customer.request, CRUD task (own only), R others"
- **Recommended fix:** Change `perm_write` to `0` for `access_agentx_customer_request_user`.
- **Status:** Open

---

### CR-2 [Blocking]
- **File:** `security/ir.model.access.csv`
- **Line:** Row `access_agentx_bug_user`
- **Dimension:** Security — ACL
- **Problem:** User group has `perm_write=1, perm_create=1` for `agentx.bug`. Spec states "Team Member: R others" — bugs fall under "others" and should be read-only for this group. This allows team members to create and modify bugs without restriction.
- **Source reference:** ODO-24 task description — "R others" covers agentx.bug
- **Recommended fix:** Change `perm_write` and `perm_create` to `0` for `access_agentx_bug_user`.
- **Status:** Open

---

### CR-3 [Blocking]
- **File:** `security/ir.model.access.csv`
- **Lines:** Rows `access_agentx_acceptance_user` and `access_agentx_acceptance_line_user`
- **Dimension:** Security — ACL
- **Problem:** User group has `perm_write=1, perm_create=1` for `agentx.acceptance` and `agentx.acceptance.line`. Spec states "Team Member: R others". Acceptance records are formal handover documentation — write access for team members is a data integrity risk.
- **Source reference:** ODO-24 task description — "R others" covers agentx.acceptance
- **Recommended fix:** Change `perm_write` and `perm_create` to `0` for user rows on both models.
- **Status:** Open

---

### CR-4 [Blocking]
- **File:** `tests/__init__.py`
- **Dimension:** Testing
- **Problem:** `tests/__init__.py` contains only a comment header. No test classes exist in the tests directory. Security-critical paths have zero automated coverage. The following paths are entirely untested:
  - Viewer cannot write any model
  - Member cannot write projects (record rule)
  - Member can only write own tasks (record rule)
  - Member can create but not write customer.requests
  - Manager has full CRUD on all models
  - Admin delete permissions
- **Source reference:** AGENTS.md §Testing — "Critical flows are not happy-path only"; Odoo review dimension #6 Testing
- **Recommended fix:** Implement `tests/test_access_control.py` with `TransactionCase` tests for each group and record rule combination.
- **Status:** Open

---

## Non-Blocking Findings

### CR-5 [Non-Blocking]
- **File:** `security/security.xml`
- **Dimension:** Blueprint alignment
- **Problem:** Group XML IDs deviate from spec-defined names. Spec requires `group_agentx_project_manager`, `group_agentx_project_member`, `group_agentx_project_viewer`. Implementation uses `group_agentx_manager`, `group_agentx_user`, `group_agentx_viewer`. External modules or automation referencing spec XML IDs will receive "External ID not found" errors.
- **Recommended fix:** Align XML IDs with spec or obtain PM approval for naming deviation and document it in blueprint.
- **Status:** Open

---

### CR-6 [Non-Blocking]
- **File:** `security/security.xml`
- **Dimension:** Scope control
- **Problem:** `group_agentx_admin` was introduced beyond the approved spec scope (spec defines 3 groups). The design rationale (segregating destructive delete into a dedicated admin tier above manager) is architecturally sound but represents an unauthorized scope expansion that was not reviewed or approved by PM.
- **Recommended fix:** Obtain PM approval to retain `group_agentx_admin`, or remove it and merge its delete permissions into `group_agentx_manager`.
- **Status:** Open

---

### CR-7 [Non-Blocking]
- **File:** `security/ir.model.access.csv`
- **Dimension:** ACL consistency
- **Problem:** Manager delete permissions are inconsistent across models. Manager has `perm_unlink=0` for: project, customer.request, sprint, task, bug. Manager has `perm_unlink=1` for: team.member, milestone, acceptance, acceptance.line, tag, resource.allocation. The spec states "Project Manager: CRUD all models" which includes delete. No documented rationale for the split.
- **Recommended fix:** (a) Grant manager delete on all models per spec, or (b) document the two-tier model and get PM approval.
- **Status:** Open

---

### CR-8 [Non-Blocking]
- **File:** `security/security.xml` — `rule_agentx_task_user`
- **Dimension:** Record rules / ORM
- **Problem:** Task record rule sets `perm_write=True` only. Members can read ALL tasks (no read restriction) and create tasks for any assignee (no create restriction). Spec states "CRUD task (own only)" implying all four operations should be scoped to own records.
- **Recommended fix:** Evaluate with PM whether full-read on all tasks is acceptable. If "own only" must apply to reads, add `perm_read=True` to the task rule and set appropriate domain.
- **Status:** Open

---

## Positive Notes

1. **Group hierarchy** — `viewer ← user ← manager ← admin` correctly implemented using `implied_ids`. Inheritance chain is sound and will propagate permissions cleanly.

2. **Record rule domains** — Both rule domain expressions are valid Odoo ORM path expressions:
   - `allocation_ids.employee_id.user_id` correctly traverses `agentx.project → agentx.team.member → hr.employee → res.users`
   - `assignee_id.user_id` and `project_id.manager_id.user_id` correctly resolve for the task rule

3. **Project access rule** — `rule_agentx_project_user` correctly restricts member read access to projects where they are manager, team_lead, or allocated resource. This matches the spec requirement and covers the `team_lead_id` field fix noted in the Coder's delivery message.

4. **ACL completeness** — All 11 new models are protected. No model is left without an ACL entry. `account.analytic.line` (inherited) correctly relies on base module ACL.

5. **Manifest load order** — Security files load before views (`security/security.xml` → `security/ir.model.access.csv` → data → reports → views). Correct Odoo convention.

6. **Bug fix preserved** — Coder's fix of invalid Python ternary expression in the record rule domain is correctly implemented. The domain syntax is clean and parseable.

---

## File-by-File Summary

| File | Dimensions Checked | Issues Found |
|------|-------------------|--------------|
| `security/security.xml` | Security, ORM, Architecture | CR-5 (NB), CR-6 (NB), CR-8 (NB) |
| `security/ir.model.access.csv` | Security, ACL completeness | CR-1 (B), CR-2 (B), CR-3 (B), CR-7 (NB) |
| `tests/__init__.py` | Testing | CR-4 (B) |
| `models/agentx_project.py` | ORM, field names | No issues |
| `models/agentx_task.py` | ORM, field names | No issues |
| `models/agentx_team_member.py` | ORM, field names | No issues |
| `__manifest__.py` | Manifest integrity | No issues |
| `models/__init__.py` | Module integrity | No issues |
| All views (9 files) | XML integrity | Not re-reviewed (unchanged from prior tasks) |

**B** = Blocking · **NB** = Non-Blocking

---

## Source References

| Reference | Location |
|-----------|----------|
| Spec: CRUD permission matrix | ODO-24 task description |
| Spec: Group names | ODO-24 task description — "Security groups to create" |
| Spec: Record rule definitions | ODO-24 task description — "Record rules" section |
| Odoo ACL convention | `base/security/ir.model.access.csv` pattern |
| Odoo record rule domains | `base/models/ir_rule.py` domain_force semantics |

---

## Revision Loop Status

| CR | Severity | Status |
|----|----------|--------|
| CR-1 | Blocking | Open — awaiting Coder fix |
| CR-2 | Blocking | Open — awaiting Coder fix |
| CR-3 | Blocking | Open — awaiting Coder fix |
| CR-4 | Blocking | Open — awaiting Coder fix |
| CR-5 | Non-Blocking | Open — awaiting PM decision |
| CR-6 | Non-Blocking | Open — awaiting PM decision |
| CR-7 | Non-Blocking | Open — awaiting PM decision |
| CR-8 | Non-Blocking | Open — awaiting PM decision |

**Next action:** Coder resolves CR-1 through CR-4 and pushes fix commits to `feature/odo-14.10`. Reviewer re-reviews changed files on next heartbeat trigger.
