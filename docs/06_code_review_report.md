# Code Review Report — ODO-23: Views Part 3: Kanban, Search & Menu

**Date:** 2026-04-16
**Reviewer:** Reviewer Agent (OdooAgentX Pipeline)
**PR:** https://github.com/khaid2849/odoo-agentx/pull/7
**Branch:** `feature/odo-14.9`
**Decision:** **NEEDS REVISION** — 3 Blocking CRs open

---

## Overall Decision

**NEEDS REVISION**

Three blocking findings prevent merge approval. Two relate to `agentx.sprint.is_overdue` (non-stored computed field used in a search domain — runtime crash) and one is a stale state value in the acceptance report QWeb template that breaks the status badge rendering. All three are small, targeted fixes. Non-blocking findings cover task_type deviation from spec, missing tests, and minor UX/naming gaps.

---

## Scope of Review

This PR implements the complete `agentx_project_management` Odoo 18 module (31 files, 4182 additions). Review covered:

- Sprint kanban view (ODO-23 primary scope)
- Task kanban and search views (pre-existing, verified)
- Menu structure completeness against spec Section 4
- All model definitions for ORM correctness
- Security (ACL, record rules, group hierarchy)
- Manifest and module integrity
- Cross-file consistency (field names, state values, group references)
- Report template state value alignment

---

## Blocking Findings

### CR-1 [Blocking]
- **File:** `models/agentx_sprint.py` lines 112–115
- **File:** `views/agentx_sprint_views.xml` line 178
- **Dimension:** ORM and Backend Logic / XML Views
- **Problem:** `agentx.sprint.is_overdue` is a non-stored computed field (`store` not set, defaults `False`) with no `search` method. The sprint search view uses `domain="[('is_overdue', '=', True)]"`. At runtime, applying this filter raises `ValueError: Cannot search on non-stored field agentx.sprint.is_overdue`. Contrast with `agentx.milestone.is_overdue` which correctly has `store=True`.
- **Source reference:** Odoo ORM — computed fields must be `store=True` or define a `search=` callback to be searchable.
- **Recommended fix:**
  ```python
  is_overdue = fields.Boolean(
      compute='_compute_is_overdue',
      string='Overdue',
      store=True,
  )
  ```
  Also add `@api.depends('state', 'date_end')` to `_compute_is_overdue` (see CR-2).
- **Status:** Open

---

### CR-2 [Blocking]
- **File:** `models/agentx_sprint.py` line 177
- **Dimension:** ORM — Computed Field Dependencies
- **Problem:** `_compute_is_overdue` on `agentx.sprint` has no `@api.depends` decorator. Without it, once `is_overdue` is made `store=True` (CR-1 fix), the field will never recompute automatically when `state` or `date_end` changes — it will stay stale at its create-time value forever.
- **Source reference:** Odoo ORM docs — stored computed fields require `@api.depends` to trigger recomputation on field changes.
- **Recommended fix:**
  ```python
  @api.depends('state', 'date_end')
  def _compute_is_overdue(self):
      today = fields.Date.today()
      for sprint in self:
          sprint.is_overdue = (
              sprint.state == 'active'
              and sprint.date_end
              and sprint.date_end < today
          )
  ```
- **Status:** Open

> **Note:** CR-1 and CR-2 must be fixed together in a single commit.

---

### CR-3 [Blocking]
- **File:** `reports/report_acceptance_template.xml` lines 22–24
- **Dimension:** XML Views / Cross-File Consistency
- **Problem:** The QWeb acceptance report template uses stale state values from the pre-ODO-18 model: `o.state == 'approved'` and `o.state == 'in_review'`. After the ODO-18 acceptance state machine refactor, these values were renamed to `accepted` and `submitted`. Since no `agentx.acceptance` record can ever have state `approved` or `in_review`, the status badge always falls through to `bg-secondary` (grey) for all accepted and submitted records.
- **Source reference:** `models/agentx_acceptance.py` state field — valid values: `draft`, `submitted`, `accepted`, `rejected`.
- **Recommended fix:**
  ```python
  #{ 'bg-success' if o.state == 'accepted' else
     'bg-danger' if o.state == 'rejected' else
     'bg-info' if o.state == 'submitted' else 'bg-secondary' }
  ```
- **Status:** Open

---

## Non-Blocking Findings

### CR-4 [Non-Blocking]
- **File:** `tests/__init__.py`
- **Dimension:** Testing
- **Problem:** `tests/__init__.py` is empty. No unit or integration tests exist. Critical business logic paths — state machine constraints (CHK-01 through CHK-06), one-active-sprint guard, acceptance gate for project closure, computed field behavior — have zero test coverage.
- **Recommended fix:** Add `TransactionCase` tests for state machine transitions, constraint enforcement, and computed field values. At minimum cover CHK-03, CHK-05, CHK-06 and the sprint one-active guard.
- **Status:** Open (for tracking; does not block this PR)

---

### CR-5 [Non-Blocking]
- **File:** `models/agentx_task.py` lines 41–51
- **Dimension:** Architecture / Spec Alignment
- **Problem:** `task_type` selection values (`story`, `task`, `improvement`) deviate from the technical spec (`feature`, `bug`, `improvement`, `research`, `documentation`). The implemented set is a different, smaller set. The search view filters (`User Stories`, `Tasks`) reflect the implemented set correctly, but the spec alignment gap should be acknowledged.
- **Recommended fix:** Confirm with PM/Architect whether this deviation was approved. If so, update the spec. If not, align to spec values.
- **Status:** Open (PM decision required)

---

### CR-6 [Non-Blocking]
- **File:** `views/menu_views.xml` line 9
- **Dimension:** Spec Alignment
- **Problem:** Root menu label is `AgentX PM`. Spec (Section 4 — Menu Structure) specifies `AgentX Projects`.
- **Recommended fix:** Either rename the menu to `AgentX Projects` or document the deviation.
- **Status:** Open

---

### CR-7 [Non-Blocking]
- **File:** `views/agentx_task_views.xml` lines 256–268 / `views/menu_views.xml` line 58
- **Dimension:** XML Views / Spec Alignment
- **Problem:** "Task Board" menu (`menu_agentx_task_board`) references `action_agentx_task` which opens in `list` mode first (`view_mode=list,kanban,form`). Spec Section 4 defines "Task Board → task kanban (all projects)". The user must manually switch to kanban.
- **Recommended fix:** Add `view_type: 'kanban'` to the action context, or create a dedicated action with `view_mode=kanban,list,form` for the Task Board menu item.
- **Status:** Open

---

## Positive Notes

1. **Sprint kanban correctness** — `view_agentx_sprint_kanban` is well-structured: `default_group_by="state"`, loads all required fields, cards show name, end date, `completion_rate` progressbar, task count, and SP progress. Spec requirement satisfied.

2. **Task search view completeness** — All spec-required filters present and correctly wired: My Tasks (`assignee_id.user_id = uid`), Overdue (deadline < today AND not done/cancelled), GroupBy Sprint/Assignee/State/Type. Well beyond spec minimum.

3. **Task kanban polish** — Uses `many2one_avatar_employee` widget for assignee, `many2many_tags` with color support for tags, `progressbar` per column — clean, idiomatic Odoo 18 kanban.

4. **Security group hierarchy** — `viewer → user → manager → admin` chain via `implied_ids` is correct. All menus properly guard with appropriate group levels.

5. **Menu action completeness** — All 16 menu `action=` references resolve to defined `ir.actions.act_window` records. No dangling XML IDs.

6. **Manifest load order** — `security/ → data/ → reports/ → views/` is correct Odoo convention.

7. **ORM create override** — `@api.model_create_multi` used consistently in all sequence-generating models (`agentx.task`, `agentx.acceptance`).

8. **State machine guards** — All action methods guard entry conditions with `UserError`. No unguarded state transitions.

9. **Acceptance gate on project closure** — `action_done` on `agentx.project` correctly blocks closure until all acceptance records have `state == 'accepted'`.

10. **Cross-file field consistency** — All fields referenced in views (`name`, `state`, `date_end`, `progress_pct`, `completion_rate`, `task_count`, `done_task_count`, `assignee_id`, `story_points`, `priority`) exist in their respective models. No broken view-to-model references found (except `reports/` — see CR-3).

---

## File-by-File Summary

| File | Dimensions Checked | Blocking | Non-Blocking |
|------|-------------------|----------|--------------|
| `models/agentx_sprint.py` | ORM, decorators, compute deps | CR-1, CR-2 | — |
| `reports/report_acceptance_template.xml` | State value consistency | CR-3 | — |
| `views/agentx_sprint_views.xml` | XML validity, field existence, kanban spec | — | — |
| `views/agentx_task_views.xml` | XML validity, kanban spec, search spec | — | CR-7 |
| `views/menu_views.xml` | Action refs, group refs, spec compliance | — | CR-6 |
| `models/agentx_task.py` | ORM correctness, task_type | — | CR-5 |
| `tests/__init__.py` | Test coverage | — | CR-4 |
| `security/security.xml` | Group hierarchy, record rules | — | — |
| `security/ir.model.access.csv` | ACL completeness | — | — |
| `__manifest__.py` | Dependencies, load order | — | — |
| `models/__init__.py` | Import completeness | — | — |
| All other models/views | ORM, field existence, XML validity | — | — |

---

## Source References

| Reference | Location |
|-----------|----------|
| Sprint kanban spec | `01_technical_spec.md` Section 4 — Sprint Kanban row |
| Task search spec | `01_technical_spec.md` Section 4 — Search View (Tasks) row |
| Menu structure spec | `01_technical_spec.md` Section 4 — Menu Structure diagram |
| Odoo non-stored field search | Odoo ORM — `fields.Boolean(compute=..., store=True)` requirement |
| Acceptance state values | `models/agentx_acceptance.py` lines 64–76 |
| Report template stale values | `reports/report_acceptance_template.xml` lines 22–24 |

---

## Revision Loop Status

| CR | Severity | Assigned To | Status |
|----|----------|-------------|--------|
| CR-1 | Blocking | Coder | Open — add `store=True` to `is_overdue` |
| CR-2 | Blocking | Coder | Open — add `@api.depends('state', 'date_end')` |
| CR-3 | Blocking | Coder | Open — fix stale state values in report template |
| CR-4 | Non-Blocking | Coder | Open — tracked for follow-up |
| CR-5 | Non-Blocking | PM decision | Open — spec alignment clarification |
| CR-6 | Non-Blocking | Coder | Open — rename menu or document deviation |
| CR-7 | Non-Blocking | Coder | Open — force kanban view for Task Board |

**Next action:** Coder resolves CR-1, CR-2, CR-3 and pushes fix commits to `feature/odo-14.9`. Reviewer re-reviews changed files on next heartbeat trigger.
