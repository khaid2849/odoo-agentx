# Code Review Report — ODO-22
**PR:** https://github.com/khaid2849/odoo-agentx/pull/6
**Branch:** `feature/odo-14.8` → `main`
**Reviewer:** Reviewer Agent (ODO pipeline — Sub-Goal 5)
**Date:** 2026-04-16
**Jira Story:** ODO-22

---

## Overall Decision

### ❌ NEEDS REVISION

**3 Blocking CRs open.** Merge blocked until all are resolved.

---

## Summary

This PR delivers the complete `agentx_project_management` Odoo 18 module, covering 8 models, state machines across all entities, views (form/list/kanban/search), security (3 groups, 27 ACL entries, 2 record rules), data (sequences, cron jobs), and QWeb reports.

The implementation is architecturally sound. State machine logic is consistent, ORM patterns are correct, security groups are properly scoped. However, three runtime defects were identified that will cause user-visible failures in production.

---

## Blocking Findings

### CR-1 [Blocking] — Sprint `is_overdue` search filter crashes on non-stored computed field

- **File:** `views/agentx_sprint_views.xml`
- **Line:** 131
- **Dimension:** XML Views — Search domain correctness
- **Problem:** The "Overdue" sprint search filter uses `domain="[('is_overdue', '=', True)]"`. The `is_overdue` field on `agentx.sprint` is a **non-stored** computed field (no `store=True`). Odoo cannot translate a domain filter on a non-stored computed field into a SQL query. Clicking "Overdue" in the sprint search will raise a `UserError: Invalid domain left operand 'is_overdue'` (or similar ORM error) at runtime.
  - Contrast: `agentx.milestone.is_overdue` is correctly defined with `store=True` and works fine.
- **Source reference:** `models/agentx_sprint.py:112-114` (no `store=True`), `views/agentx_sprint_views.xml:131`
- **Recommended fix (two options):**
  1. Add `store=True` to `agentx.sprint.is_overdue` and add `@api.depends('state', 'date_end')` to `_compute_is_overdue`. The field value will then be stored in DB and the search will work.
  2. Replace the filter domain with the underlying computed expression: `domain="[('state', '=', 'active'), ('date_end', '&lt;', context_today().strftime('%Y-%m-%d'))]"`
- **Status:** Open

---

### CR-2 [Blocking] — Print PDF header button action name missing module prefix

- **File:** `views/agentx_acceptance_views.xml`
- **Line:** 61-63
- **Dimension:** XML Views — Action reference correctness
- **Problem:** The Print PDF button is:
  ```xml
  <button name="action_report_agentx_acceptance"
          string="Print PDF" type="action"
          class="btn-secondary"/>
  ```
  For `type="action"` header buttons in Odoo 17/18, the `name` attribute must be a **fully-qualified external ID** (`module.xmlid`). The Odoo web client passes this string directly to `actionService.doAction()`, which resolves it via `ir.model.data`. Using just `action_report_agentx_acceptance` (without the module prefix) fails with an action-not-found error when clicked.
  - Note: The report is already bound to the model via `binding_model_id` + `binding_type="report"`, so it does appear in the Action → Print menu. However, the dedicated header button — which is the spec-required deliverable for ODO-22 — will not work.
- **Source reference:** `views/agentx_acceptance_views.xml:61`, `reports/report_action.xml:7`
- **Recommended fix:** Change the button to:
  ```xml
  <button name="agentx_project_management.action_report_agentx_acceptance"
          string="Print PDF" type="action"
          class="btn-secondary"/>
  ```
  Alternatively, use `type="object"` pointing to a Python method that returns the report action.
- **Status:** Open

---

### CR-3 [Blocking] — Sprint velocity set to total story points instead of completed story points

- **File:** `models/agentx_sprint.py`
- **Line:** 213
- **Dimension:** ORM and Backend Logic — Computed business logic correctness
- **Problem:** In `action_complete()`:
  ```python
  sprint.velocity = sprint.total_story_points if sprint.done_task_count else 0
  ```
  This sets `velocity` to **total story points of all tasks** whenever at least one task is done. Velocity is an agile metric that measures *completed work only* (`completed_story_points`). For example, in a sprint with 30 total SP and 15 done SP, this code records velocity as 30 (incorrect) instead of 15 (correct).
  - The correct field is already computed and stored: `sprint.completed_story_points`.
- **Source reference:** `models/agentx_sprint.py:213`
- **Recommended fix:**
  ```python
  sprint.velocity = sprint.completed_story_points
  ```
- **Status:** Open

---

## Non-Blocking Findings

### CR-4 [Non-Blocking] — No unit tests

- **File:** `tests/__init__.py`
- **Line:** 1-2
- **Dimension:** Testing
- **Problem:** The tests directory is empty. No test classes, no state machine transition tests, no constraint validation tests. Blueprint section 6 and the QA gate require unit test coverage of business logic and edge cases.
- **Recommended fix:** Add `TransactionCase` tests for: (a) each state machine's happy path and invalid transitions, (b) CHK-01 through CHK-06 constraint validations, (c) the `_check_one_active_sprint` constraint, (d) acceptance `action_accept()` rejection guard.
- **Status:** Open (non-blocking for this delivery; should be addressed in a follow-up)

---

### CR-5 [Non-Blocking] — N+1 query pattern in stat button compute methods

- **File:** `models/agentx_project.py`
- **Lines:** 190-213
- **Dimension:** Performance
- **Problem:** `_compute_sprint_count`, `_compute_task_count`, `_compute_bug_count`, `_compute_request_count` all use `len(project.X_ids)` which loads entire One2many recordsets into memory per project record. On a list view with 100 projects, this is 100 × N record loads. Odoo provides `read_group` for efficient counting.
- **Recommended fix:** Use `self.env['agentx.sprint'].read_group([('project_id', 'in', self.ids)], ['project_id'], ['project_id'])` pattern and map the counts to each project in a single query.
- **Status:** Open (acceptable for V1; flag for performance milestone)

---

### CR-6 [Non-Blocking] — `_compute_is_overdue` on `agentx.sprint` missing `@api.depends`

- **File:** `models/agentx_sprint.py`
- **Lines:** 177-184
- **Dimension:** ORM and Backend Logic
- **Problem:** `_compute_is_overdue` has no `@api.depends` decorator. Without it, the ORM cannot know which field changes should trigger recomputation. Non-stored computed fields without `@api.depends` are recomputed on every access (no cache), which works but is inefficient and can produce stale values within the same transaction.
- **Recommended fix:**
  ```python
  @api.depends('state', 'date_end')
  def _compute_is_overdue(self):
  ```
- **Status:** Open (note: milestone model correctly has `@api.depends` on its equivalent method)

---

### CR-7 [Non-Blocking] — Sprint completion silently allows in-progress tasks

- **File:** `models/agentx_sprint.py`
- **Lines:** 205-211
- **Dimension:** ORM and Backend Logic
- **Problem:** `action_complete()` logs a Python warning when in-progress tasks exist but does NOT surface it to the user. The sprint silently completes with tasks stranded. This is a data integrity risk — tasks transition to `in_progress` state under a completed sprint without any UI signal.
- **Recommended fix:** Either raise a `UserError` (strict policy), or use the Odoo warning return dict `{'warning': {'title': ..., 'message': ...}}` to show a blocking dialog before completion. The `confirm=` attribute on the XML button provides a pre-flight prompt but does not convey the in-progress count.
- **Status:** Open

---

## Positive Notes

- **Correct ORM patterns throughout:** `@api.model_create_multi`, `super()` in all `create()` overrides, `ensure_one()` in smart button actions — all correct.
- **State machine guards are consistently applied:** Every action method checks the current state before transition and raises a meaningful `UserError` if invalid. This prevents data corruption from concurrent multi-record actions.
- **Security scoping is well-structured:** Group hierarchy (user → manager → admin) with implied group inheritance is idiomatic Odoo. ACL matrix (27 entries) covers all 9 custom models with correct role-based permissions.
- **Sequence-based auto-codes:** All major entities (`agentx.task`, `agentx.bug`, `agentx.acceptance`, etc.) use `ir.sequence` for auto-generated codes — correct approach.
- **Tracking and chatter:** All state changes use `tracking=True` and `message_post()`, ensuring full audit trail.
- **CHK-03, CHK-05, CHK-06 constraints:** Sprint-within-project date guards and allocation deduplication are correctly implemented using `@api.constrains`.
- **`_check_one_active_sprint` constraint:** Correctly prevents multiple concurrent active sprints per project.
- **Acceptance `action_accept()` blocks on failed criteria:** Guard against accepting records with `result='fail'` lines is the right business logic.
- **`action_done()` project closure guard:** Both the open-bug check and the all-acceptances-accepted check are properly enforced before project closure.

---

## Source Code References

| Finding | File | Line(s) | Severity |
|---------|------|---------|----------|
| CR-1: Sprint is_overdue search | `views/agentx_sprint_views.xml` | 131 | Blocking |
| CR-1: Sprint is_overdue field (non-stored) | `models/agentx_sprint.py` | 112-114 | Blocking |
| CR-2: Print PDF button name | `views/agentx_acceptance_views.xml` | 61-63 | Blocking |
| CR-2: Report action definition | `reports/report_action.xml` | 7-16 | Reference |
| CR-3: Velocity calculation | `models/agentx_sprint.py` | 213 | Blocking |
| CR-4: Empty tests dir | `tests/__init__.py` | — | Non-Blocking |
| CR-5: N+1 compute | `models/agentx_project.py` | 190-213 | Non-Blocking |
| CR-6: Missing @api.depends | `models/agentx_sprint.py` | 177 | Non-Blocking |
| CR-7: Silent sprint completion | `models/agentx_sprint.py` | 205-211 | Non-Blocking |

---

## Next Action

**Coder must resolve CR-1, CR-2, CR-3 before re-review.**

Fixes are surgical — no architectural changes required:
1. Fix `is_overdue` on `agentx.sprint`: add `store=True` + `@api.depends`
2. Fix Print PDF button: add `agentx_project_management.` prefix to action name
3. Fix velocity: change to `sprint.completed_story_points`

Re-review will cover only changed files and will be fast.
