# -*- coding: utf-8 -*-
"""
Unit tests for agentx.task model.

Covers:
- State machine transitions (backlog → todo → in_progress → in_review → done, blocked path, cancel/reopen)
- Sprint-project constraint (sprint must belong to same project)
- CHK-05: task in 'todo' state must have a sprint assigned
- Code auto-generation via ir.sequence
"""
import datetime

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged('post_install', '-at_install', 'agentx_task')
class TestTaskStateMachine(TransactionCase):
    """Test state machine transitions on agentx.task."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env['hr.employee'].create({'name': 'PM Task SM'})
        cls.project = cls.env['agentx.project'].create({
            'name': 'Task SM Project',
            'code': 'TSM',
            'date_start': datetime.date(2025, 1, 1),
            'date_end': datetime.date(2025, 12, 31),
            'state': 'active',
            'manager_id': cls.employee.id,
        })
        cls.sprint = cls.env['agentx.sprint'].create({
            'name': 'Task Sprint',
            'project_id': cls.project.id,
            'date_start': datetime.date(2025, 2, 1),
            'date_end': datetime.date(2025, 2, 28),
            'state': 'active',
        })

    def _make_task(self, state='backlog', with_sprint=False):
        vals = {
            'name': 'Test Task',
            'project_id': self.project.id,
        }
        if with_sprint:
            vals['sprint_id'] = self.sprint.id
        task = self.env['agentx.task'].create(vals)
        if state != 'backlog':
            task.write({'state': state})
        return task

    # ------------------------------------------------------------------
    # backlog → todo
    # ------------------------------------------------------------------
    def test_action_plan_from_backlog(self):
        task = self._make_task(with_sprint=True)
        task.action_plan()
        self.assertEqual(task.state, 'todo')

    def test_action_plan_not_from_backlog_raises(self):
        task = self._make_task(state='in_progress')
        with self.assertRaises(UserError):
            task.action_plan()

    # ------------------------------------------------------------------
    # todo → in_progress
    # ------------------------------------------------------------------
    def test_action_start_from_todo(self):
        task = self._make_task(state='todo', with_sprint=True)
        task.action_start()
        self.assertEqual(task.state, 'in_progress')
        self.assertTrue(task.date_started)

    def test_action_start_from_blocked(self):
        task = self._make_task(state='blocked')
        task.action_start()
        self.assertEqual(task.state, 'in_progress')

    def test_action_start_from_backlog_raises(self):
        task = self._make_task()
        with self.assertRaises(UserError):
            task.action_start()

    # ------------------------------------------------------------------
    # in_progress → blocked
    # ------------------------------------------------------------------
    def test_action_block_from_in_progress(self):
        task = self._make_task(state='in_progress')
        task.write({'block_reason': 'Waiting for API spec'})
        task.action_block()
        self.assertEqual(task.state, 'blocked')

    def test_action_block_not_from_in_progress_raises(self):
        task = self._make_task(state='todo', with_sprint=True)
        with self.assertRaises(UserError):
            task.action_block()

    # ------------------------------------------------------------------
    # blocked → in_progress
    # ------------------------------------------------------------------
    def test_action_unblock(self):
        task = self._make_task(state='blocked')
        task.action_unblock()
        self.assertEqual(task.state, 'in_progress')
        self.assertFalse(task.block_reason)

    def test_action_unblock_not_from_blocked_raises(self):
        task = self._make_task(state='in_progress')
        with self.assertRaises(UserError):
            task.action_unblock()

    # ------------------------------------------------------------------
    # in_progress → in_review
    # ------------------------------------------------------------------
    def test_action_submit_review(self):
        task = self._make_task(state='in_progress')
        task.action_submit_review()
        self.assertEqual(task.state, 'in_review')

    def test_action_submit_review_not_from_in_progress_raises(self):
        task = self._make_task(state='todo', with_sprint=True)
        with self.assertRaises(UserError):
            task.action_submit_review()

    # ------------------------------------------------------------------
    # in_review → in_progress (reject)
    # ------------------------------------------------------------------
    def test_action_reject_review(self):
        task = self._make_task(state='in_review')
        task.action_reject_review()
        self.assertEqual(task.state, 'in_progress')

    def test_action_reject_review_not_from_in_review_raises(self):
        task = self._make_task(state='in_progress')
        with self.assertRaises(UserError):
            task.action_reject_review()

    # ------------------------------------------------------------------
    # in_review → done
    # ------------------------------------------------------------------
    def test_action_done_from_in_review(self):
        task = self._make_task(state='in_review')
        task.action_done()
        self.assertEqual(task.state, 'done')
        self.assertTrue(task.date_done)

    def test_action_done_not_from_in_review_raises(self):
        task = self._make_task(state='in_progress')
        with self.assertRaises(UserError):
            task.action_done()

    # ------------------------------------------------------------------
    # any open state → cancelled
    # ------------------------------------------------------------------
    def test_action_cancel_from_backlog(self):
        task = self._make_task()
        task.action_cancel()
        self.assertEqual(task.state, 'cancelled')

    def test_action_cancel_from_in_progress(self):
        task = self._make_task(state='in_progress')
        task.action_cancel()
        self.assertEqual(task.state, 'cancelled')

    def test_action_cancel_from_done_raises(self):
        task = self._make_task(state='done')
        with self.assertRaises(UserError):
            task.action_cancel()

    def test_action_cancel_from_cancelled_raises(self):
        task = self._make_task(state='cancelled')
        with self.assertRaises(UserError):
            task.action_cancel()

    # ------------------------------------------------------------------
    # done/cancelled → backlog (reopen)
    # ------------------------------------------------------------------
    def test_action_reopen_from_done(self):
        task = self._make_task(state='done')
        task.action_reopen()
        self.assertEqual(task.state, 'backlog')
        self.assertFalse(task.date_done)

    def test_action_reopen_from_cancelled(self):
        task = self._make_task(state='cancelled')
        task.action_reopen()
        self.assertEqual(task.state, 'backlog')

    def test_action_reopen_from_in_progress_raises(self):
        task = self._make_task(state='in_progress')
        with self.assertRaises(UserError):
            task.action_reopen()


@tagged('post_install', '-at_install', 'agentx_task')
class TestTaskConstraints(TransactionCase):
    """Test sprint-project constraint and CHK-05 on agentx.task."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env['hr.employee'].create({'name': 'PM Task Constraint'})
        cls.project_a = cls.env['agentx.project'].create({
            'name': 'Project A',
            'code': 'TCA',
            'date_start': datetime.date(2025, 1, 1),
            'date_end': datetime.date(2025, 12, 31),
            'state': 'active',
            'manager_id': cls.employee.id,
        })
        cls.project_b = cls.env['agentx.project'].create({
            'name': 'Project B',
            'code': 'TCB',
            'date_start': datetime.date(2025, 1, 1),
            'date_end': datetime.date(2025, 12, 31),
            'state': 'active',
            'manager_id': cls.employee.id,
        })
        cls.sprint_a = cls.env['agentx.sprint'].create({
            'name': 'Sprint A',
            'project_id': cls.project_a.id,
            'date_start': datetime.date(2025, 2, 1),
            'date_end': datetime.date(2025, 2, 28),
        })

    def test_sprint_must_belong_to_same_project(self):
        with self.assertRaises(ValidationError):
            self.env['agentx.task'].create({
                'name': 'Cross-project Task',
                'project_id': self.project_b.id,
                'sprint_id': self.sprint_a.id,
            })

    def test_sprint_same_project_is_valid(self):
        task = self.env['agentx.task'].create({
            'name': 'Valid Sprint Task',
            'project_id': self.project_a.id,
            'sprint_id': self.sprint_a.id,
        })
        self.assertEqual(task.sprint_id, self.sprint_a)

    def test_chk05_todo_without_sprint_raises(self):
        """CHK-05: Moving a task to 'todo' without a sprint should raise."""
        with self.assertRaises(ValidationError):
            self.env['agentx.task'].create({
                'name': 'No Sprint Todo Task',
                'project_id': self.project_a.id,
                'state': 'todo',
            })

    def test_chk05_todo_with_sprint_is_valid(self):
        task = self.env['agentx.task'].create({
            'name': 'Sprint Todo Task',
            'project_id': self.project_a.id,
            'sprint_id': self.sprint_a.id,
            'state': 'todo',
        })
        self.assertEqual(task.state, 'todo')


@tagged('post_install', '-at_install', 'agentx_task')
class TestTaskCodeAutoGeneration(TransactionCase):
    """Test that agentx.task.code is auto-generated via ir.sequence."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env['hr.employee'].create({'name': 'PM Task Code'})
        cls.project = cls.env['agentx.project'].create({
            'name': 'Code Gen Project',
            'code': 'CGP',
            'date_start': datetime.date.today(),
            'manager_id': cls.employee.id,
        })

    def test_task_code_is_generated_on_create(self):
        task = self.env['agentx.task'].create({
            'name': 'Code Auto Task',
            'project_id': self.project.id,
        })
        self.assertTrue(task.code)
        self.assertNotEqual(task.code, '/')

    def test_task_code_starts_with_task_prefix(self):
        task = self.env['agentx.task'].create({
            'name': 'Prefix Check Task',
            'project_id': self.project.id,
        })
        self.assertTrue(task.code.startswith('TASK-'))

    def test_task_codes_are_unique(self):
        task1 = self.env['agentx.task'].create({
            'name': 'Task One',
            'project_id': self.project.id,
        })
        task2 = self.env['agentx.task'].create({
            'name': 'Task Two',
            'project_id': self.project.id,
        })
        self.assertNotEqual(task1.code, task2.code)
