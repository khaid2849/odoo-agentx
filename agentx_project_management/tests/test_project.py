# -*- coding: utf-8 -*-
"""
Unit tests for agentx.project model.

Covers:
- State machine transitions (draft → active → done/cancelled/on_hold, etc.)
- Constraint: duplicate project code
- Constraint: end date before start date
- Constraint: open bugs block project close
- completion_rate computed field
"""
import datetime

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged('post_install', '-at_install', 'agentx_project')
class TestProjectStateMachine(TransactionCase):
    """Test state machine transitions on agentx.project."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env['hr.employee'].create({'name': 'PM State Test'})
        cls.project = cls.env['agentx.project'].create({
            'name': 'State Machine Project',
            'code': 'SMP',
            'date_start': datetime.date.today(),
            'manager_id': cls.employee.id,
        })

    def setUp(self):
        super().setUp()
        # Reset state to draft before each test
        self.project.write({'state': 'draft'})

    # ------------------------------------------------------------------
    # draft → active
    # ------------------------------------------------------------------
    def test_action_start_from_draft(self):
        self.assertEqual(self.project.state, 'draft')
        self.project.action_start()
        self.assertEqual(self.project.state, 'active')

    def test_action_start_not_from_draft_raises(self):
        self.project.write({'state': 'active'})
        with self.assertRaises(UserError):
            self.project.action_start()

    # ------------------------------------------------------------------
    # active → on_hold
    # ------------------------------------------------------------------
    def test_action_hold_from_active(self):
        self.project.write({'state': 'active'})
        self.project.action_hold()
        self.assertEqual(self.project.state, 'on_hold')

    def test_action_hold_not_from_active_raises(self):
        with self.assertRaises(UserError):
            self.project.action_hold()

    # ------------------------------------------------------------------
    # on_hold → active
    # ------------------------------------------------------------------
    def test_action_reactivate_from_on_hold(self):
        self.project.write({'state': 'on_hold'})
        self.project.action_reactivate()
        self.assertEqual(self.project.state, 'active')

    def test_action_reactivate_not_from_on_hold_raises(self):
        with self.assertRaises(UserError):
            self.project.action_reactivate()

    # ------------------------------------------------------------------
    # active → done (happy path: no open bugs)
    # ------------------------------------------------------------------
    def test_action_done_from_active_no_open_bugs(self):
        self.project.write({'state': 'active'})
        self.project.action_done()
        self.assertEqual(self.project.state, 'done')

    def test_action_done_not_from_active_raises(self):
        with self.assertRaises(UserError):
            self.project.action_done()

    # ------------------------------------------------------------------
    # active → done blocked by open bugs
    # ------------------------------------------------------------------
    def test_action_done_blocked_by_open_bugs(self):
        self.project.write({'state': 'active'})
        # Create an open bug (state='new')
        self.env['agentx.bug'].create({
            'name': 'Blocking Bug',
            'project_id': self.project.id,
        })
        with self.assertRaises(UserError):
            self.project.action_done()

    def test_action_done_succeeds_when_all_bugs_closed(self):
        self.project.write({'state': 'active'})
        bug = self.env['agentx.bug'].create({
            'name': 'Resolved Bug',
            'project_id': self.project.id,
        })
        bug.write({'state': 'closed'})
        self.project.action_done()
        self.assertEqual(self.project.state, 'done')

    # ------------------------------------------------------------------
    # draft/active/on_hold → cancelled
    # ------------------------------------------------------------------
    def test_action_cancel_from_draft(self):
        self.project.action_cancel()
        self.assertEqual(self.project.state, 'cancelled')

    def test_action_cancel_from_active(self):
        self.project.write({'state': 'active'})
        self.project.action_cancel()
        self.assertEqual(self.project.state, 'cancelled')

    def test_action_cancel_from_on_hold(self):
        self.project.write({'state': 'on_hold'})
        self.project.action_cancel()
        self.assertEqual(self.project.state, 'cancelled')

    def test_action_cancel_from_done_raises(self):
        self.project.write({'state': 'done'})
        with self.assertRaises(UserError):
            self.project.action_cancel()

    # ------------------------------------------------------------------
    # cancelled → draft
    # ------------------------------------------------------------------
    def test_action_reset_to_draft_from_cancelled(self):
        self.project.write({'state': 'cancelled'})
        self.project.action_reset_to_draft()
        self.assertEqual(self.project.state, 'draft')

    def test_action_reset_to_draft_not_from_cancelled_raises(self):
        with self.assertRaises(UserError):
            self.project.action_reset_to_draft()


@tagged('post_install', '-at_install', 'agentx_project')
class TestProjectConstraints(TransactionCase):
    """Test database and Python constraints on agentx.project."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env['hr.employee'].create({'name': 'PM Constraint Test'})

    def _make_project(self, code='PRJ', **kwargs):
        vals = {
            'name': 'Constraint Project',
            'code': code,
            'date_start': datetime.date(2025, 1, 1),
            'manager_id': self.employee.id,
        }
        vals.update(kwargs)
        return self.env['agentx.project'].create(vals)

    def test_duplicate_code_raises(self):
        self._make_project(code='DUP')
        with self.assertRaises(Exception):
            self._make_project(code='DUP')

    def test_end_date_before_start_date_raises(self):
        with self.assertRaises(ValidationError):
            self._make_project(
                code='DATES',
                date_start=datetime.date(2025, 6, 1),
                date_end=datetime.date(2025, 1, 1),
            )

    def test_end_date_equal_to_start_date_is_valid(self):
        proj = self._make_project(
            code='EQDATES',
            date_start=datetime.date(2025, 6, 1),
            date_end=datetime.date(2025, 6, 1),
        )
        self.assertTrue(proj.id)

    def test_no_end_date_is_valid(self):
        proj = self._make_project(code='NOEND')
        self.assertFalse(proj.date_end)


@tagged('post_install', '-at_install', 'agentx_project')
class TestProjectCompletionRate(TransactionCase):
    """Test completion_rate computed field on agentx.project."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env['hr.employee'].create({'name': 'PM Completion Test'})
        cls.project = cls.env['agentx.project'].create({
            'name': 'Completion Rate Project',
            'code': 'CRP',
            'date_start': datetime.date.today(),
            'manager_id': cls.employee.id,
        })
        # Create a sprint so tasks can move to 'todo'
        cls.sprint = cls.env['agentx.sprint'].create({
            'name': 'Sprint 1',
            'project_id': cls.project.id,
            'date_start': datetime.date.today(),
            'date_end': datetime.date.today() + datetime.timedelta(days=14),
        })

    def _create_task(self, state='backlog'):
        task = self.env['agentx.task'].create({
            'name': 'Test Task',
            'project_id': self.project.id,
        })
        if state != 'backlog':
            task.write({'state': state})
        return task

    def test_completion_rate_zero_with_no_tasks(self):
        project = self.env['agentx.project'].create({
            'name': 'Empty Project',
            'code': 'EMPT',
            'date_start': datetime.date.today(),
            'manager_id': self.employee.id,
        })
        self.assertEqual(project.completion_rate, 0.0)

    def test_completion_rate_100_when_all_done(self):
        project = self.env['agentx.project'].create({
            'name': 'All Done Project',
            'code': 'DONE',
            'date_start': datetime.date.today(),
            'manager_id': self.employee.id,
        })
        for i in range(3):
            self.env['agentx.task'].create({
                'name': f'Task {i}',
                'project_id': project.id,
                'state': 'done',
            })
        self.assertAlmostEqual(project.completion_rate, 100.0, places=1)

    def test_completion_rate_partial(self):
        project = self.env['agentx.project'].create({
            'name': 'Partial Project',
            'code': 'PART',
            'date_start': datetime.date.today(),
            'manager_id': self.employee.id,
        })
        for i in range(4):
            state = 'done' if i < 2 else 'in_progress'
            self.env['agentx.task'].create({
                'name': f'Task {i}',
                'project_id': project.id,
                'state': state,
            })
        self.assertAlmostEqual(project.completion_rate, 50.0, places=1)
