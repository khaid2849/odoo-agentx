# Code Review Report — ODO-24: Access Control & Security

**Module:** `agentx_project_management`
**Feature Branch:** `feature/odo-14.10`
**PR:** https://github.com/khaid2849/odoo-agentx/pull/8
**Reviewer:** Reviewer Agent (ODO-24)
**Review Rounds:** 2
**Final Decision:** ✅ **APPROVED**
**Date:** 2026-04-17

---

## Overall Decision

**APPROVED** — All 6 blocking CRs resolved. Security implementation is correct, complete, and aligned with the specification. Ready to merge.

---

## Review Round 1 — Decision: NEEDS REVISION

Initial review found 4 blocking CRs (permission over-grants and empty tests), plus 4 non-blocking items. PM escalated CR-5 (group name mismatch) and CR-7 (inconsistent manager delete) to blocking.

**Blocking CRs after PM decisions: 6 total.**

---

## Review Round 2 — All Blocking CRs Resolved

Fix commit: `f17a925` — _fix(ODO-24): address all 6 blocking CRs from security review_

### CR Resolution Table

| CR | Severity | Status | Fix Verified |
|----|----------|--------|--------------|
| CR-1 | High | ✅ Resolved | `customer.request` member row: `1,0,1,0` (CR only — no write) |
| CR-2 | High | ✅ Resolved | `bug` member row: `1,0,0,0` (read-only) |
| CR-3 | High | ✅ Resolved | `acceptance` + `acceptance.line` member rows: `1,0,0,0` (read-only) |
| CR-4 | Medium | ✅ Resolved | `tests/test_security.py` added (12 tests); `tests/__init__.py` imports it |
| CR-5 | Blocking | ✅ Resolved | Groups renamed: `group_agentx_project_viewer/member/manager` — all XML/CSV refs updated |
| CR-6 | Non-Blocking | ✅ Approved | `group_agentx_admin` retained per PM decision |
| CR-7 | Blocking | ✅ Resolved | All 11 manager rows have `perm_unlink=1` (consistent CRUD) |
| CR-8 | Non-Blocking | ✅ Accepted | Task read restriction scope acknowledged; PM approved current behavior |

---

## File-by-File Findings

### `security/ir.model.access.csv`

**Decision: APPROVED**

- 44 rows, 11 models × 4 groups — coverage complete
- Permission matrix verified against spec:

| Model | Viewer | Member | Manager | Admin |
|-------|--------|--------|---------|-------|
| `agentx.project` | R | R | CRUD | CRUD |
| `agentx.customer.request` | R | R+C | CRUD | CRUD |
| `agentx.sprint` | R | R | CRUD | CRUD |
| `agentx.task` | R | RWC | CRUD | CRUD |
| `agentx.bug` | R | R | CRUD | CRUD |
| `agentx.team.member` | R | R | CRUD | CRUD |
| `agentx.milestone` | R | R | CRUD | CRUD |
| `agentx.acceptance` | R | R | CRUD | CRUD |
| `agentx.acceptance.line` | R | R | CRUD | CRUD |
| `agentx.tag` | R | R | CRUD | CRUD |
| `agentx.resource.allocation` | R | R | CRUD | CRUD |

All manager `perm_unlink` values are `1` — consistent with spec "CRUD all models".

### `security/security.xml`

**Decision: APPROVED**

- Group hierarchy: `viewer ← member ← manager ← admin` via `implied_ids` — correct
- All group IDs match spec exactly:
  - `group_agentx_project_viewer`
  - `group_agentx_project_member`
  - `group_agentx_project_manager`
  - `group_agentx_admin` (PM-approved extra group)
- Record rules:
  - `rule_agentx_project_user`: domain `['|', '|', manager_id.user_id=uid, team_lead_id.user_id=uid, allocation_ids.employee_id.user_id=uid]` — correct, applies to member group, perm_read only
  - `rule_agentx_task_user`: domain `['|', assignee_id.user_id=uid, project_id.manager_id.user_id=uid]` — correct, applies to member group, perm_write only
- No stale old group name references anywhere (`group_agentx_user`, `group_agentx_manager`, `group_agentx_viewer` — all gone)

### `tests/test_security.py`

**Decision: APPROVED**

- 12 test methods across 2 test classes: `TestSecurityGroups` and `TestRecordRules`
- Uses `TransactionCase` with `@tagged('post_install', '-at_install', 'security')` — correct Odoo test pattern
- Coverage includes:
  - Viewer: read allowed, write/create blocked
  - Member: customer.request create allowed, write blocked; bug read OK, create/write blocked; acceptance create/write blocked
  - Manager: create + delete on project, bug, acceptance
  - Record rules: member cannot write unrelated project; member cannot write task assigned to other member
- `tests/__init__.py` updated: `from . import test_security` — tests will be discovered

### `views/agentx_acceptance_views.xml`

**Decision: APPROVED**

- `action_accept` and `action_reject` buttons now reference `group_agentx_project_manager` — correct

### `views/menu_views.xml`

**Decision: APPROVED**

- All menu visibility references updated from old group IDs to spec-correct IDs
- No stale references remaining

---

## Positive Notes

- Group hierarchy via `implied_ids` is elegant and correct — a Viewer can be promoted to Member without re-granting permissions
- Record rule domains are valid ORM path expressions, no Python runtime risk
- ACL coverage is complete: all 11 models covered, 44 rows, none missed
- Manifest load order is correct (security files before views)
- Test setup uses `no_reset_password=True` context — correct for test user creation in Odoo 17/18
- Commit message is detailed and clearly maps each fix to a CR

---

## Source Code References

| File | Lines | Finding |
|------|-------|---------|
| `security/ir.model.access.csv` | 7 | CR-1: customer.request member = `1,0,1,0` ✅ |
| `security/ir.model.access.csv` | 19 | CR-2: bug member = `1,0,0,0` ✅ |
| `security/ir.model.access.csv` | 31, 35 | CR-3: acceptance + line member = `1,0,0,0` ✅ |
| `security/ir.model.access.csv` | 4,8,12,16,20,24,28,32,36,40,44 | CR-7: all manager rows `perm_unlink=1` ✅ |
| `security/security.xml` | 10,18,26 | CR-5: group IDs match spec exactly ✅ |
| `tests/__init__.py` | 2 | CR-4: imports test_security ✅ |
| `tests/test_security.py` | 1–235 | CR-4: 12 tests, 2 test classes ✅ |

---

## Final Summary

All blocking issues resolved. Security implementation is production-ready:

- ACL matrix faithfully implements the spec permission table
- Record rules enforce row-level isolation for members
- Group hierarchy is correctly layered
- Tests cover critical security boundaries
- No stale group ID references remain anywhere in the codebase

**Decision: APPROVED — merge `feature/odo-14.10` → `main`**
