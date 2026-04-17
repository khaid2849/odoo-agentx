# -*- coding: utf-8 -*-
"""
Unit tests for agentx.sprint model.

Covers:
- State machine transitions (planning → active → completed/cancelled)
- One-active-sprint-per-project constraint
- Velocity auto-set on completion
- Overdue detection via is_overdue computed field
"""
import datetime

from odoo.exceptions import UserError, ValidationError
from odoo import fields
from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged('post_install', '-at_install', 'agentx_sprint')
class TestSprintStateMachine(TransactionCase):
    """Test state machine transitions on agentx.sprint."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env['hr.employee'].create({'name': 'PM Sprint SM'})
        cls.project = cls.env['agentx.project'].create({
            'name': 'Sprint SM Project',
            'code': 'SSM',
            'date_start': datetime.date(2025, 1, 1),
            'date_end': datetime.date(2025, 12, 31),
            'state': 'active',
            'manager_id': cls.employee.id,
        })

    def _make_sprint(self, name='Sprint', state='planning', **kwargs):
        vals = {
            'name': name,
            'project_id': self.project.id,
            'date_start': datetime.date(2025, 2, 1),
            'date_end': datetime.date(2025, 2, 28),
        }
        vals.update(kwargs)
        sprint = self.env['agentx.sprint'].create(vals)
        if state != 'planning':
            sprint.write({'state': state})
        return sprint

    # ------------------------------------------------------------------
    # planning → active
    # ------------------------------------------------------------------
    def test_action_start_from_planning(self):
        sprint = self._make_sprint('Sprint Start')
        sprint.action_start()
        self.assertEqual(sprint.state, 'active')

    def test_action_start_not_from_planning_raises(self):
        sprint = self._make_sprint('Sprint Already Active', state='active')
        with self.assertRaises(UserError):
            sprint.action_start()

    def test_action_start_on_inactive_project_raises(self):
        project = self.env['agentx.project'].create({
            'name': 'Inactive Project',
            'code': 'INA',
            'date_start': datetime.date(2025, 1, 1),
            'manager_id': self.employee.id,
            'state': 'draft',
        })
        sprint = self.env['agentx.sprint'].create({
            'name': 'Sprint on Draft Project',
            'project_id': project.id,
            'date_start': datetime.date(2025, 2, 1),
            'date_end': datetime.date(2025, 2, 28),
        })
        with self.assertRaises(UserError):
            sprint.action_start()

    # ------------------------------------------------------------------
    # active → completed
    # ------------------------------------------------------------------
    def test_action_complete_from_active(self):
        sprint = self._make_sprint('Sprint Complete', state='active')
        sprint.action_complete()
        self.assertEqual(sprint.state, 'completed')

    def test_action_complete_not_from_active_raises(self):
        sprint = self._make_sprint('Sprint Planning Complete')
        with self.assertRaises(UserError):
            sprint.action_complete()

    # ------------------------------------------------------------------
    # planning/active → cancelled
    # ------------------------------------------------------------------
    def test_action_cancel_from_planning(self):
        sprint = self._make_sprint('Sprint Cancel Planning')
        sprint.action_cancel()
        self.assertEqual(sprint.state, 'cancelled')

    def test_action_cancel_from_active(self):
        sprint = self._make_sprint('Sprint Cancel Active', state='active')
        sprint.action_cancel()
        self.assertEqual(sprint.state, 'cancelled')

    def test_action_cancel_from_completed_raises(self):
        sprint = self._make_sprint('Sprint Cancel Completed', state='completed')
        with self.assertRaises(UserError):
            sprint.action_cancel()

    # ------------------------------------------------------------------
    # cancelled → planning
    # ------------------------------------------------------------------
    def test_action_reset_to_planning_from_cancelled(self):
        sprint = self._make_sprint('Sprint Reset', state='cancelled')
        sprint.action_reset_to_planning()
        self.assertEqual(sprint.state, 'planning')

    def test_action_reset_to_planning_not_from_cancelled_raises(self):
        sprint = self._make_sprint('Sprint Not Cancelled')
        with self.assertRaises(UserError):
            sprint.action_reset_to_planning()


@tagged('post_install', '-at_install', 'agentx_sprint')
class TestSprintOneActiveConstraint(TransactionCase):
    """Test that only one active sprint is allowed per project."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env['hr.employee'].create({'name': 'PM One Active'})
        cls.project = cls.env['agentx.project'].create({
            'name': 'One Active Sprint Project',
            'code': 'OAS',
            'date_start': datetime.date(2025, 1, 1),
            'date_end': datetime.date(2025, 12, 31),
            'state': 'active',
            'manager_id': cls.employee.id,
        })

    def test_two_active_sprints_raises(self):
        self.env['agentx.sprint'].create({
            'name': 'Active Sprint 1',
            'project_id': self.project.id,
            'date_start': datetime.date(2025, 1, 1),
            'date_end': datetime.date(2025, 1, 31),
            'state': 'active',
        })
        with self.assertRaises(ValidationError):
            self.env['agentx.sprint'].create({
                'name': 'Active Sprint 2',
                'project_id': self.project.id,
                'date_start': datetime.date(2025, 2, 1),
                'date_end': datetime.date(2025, 2, 28),
                'state': 'active',
            })

    def test_active_in_different_projects_is_allowed(self):
        project2 = self.env['agentx.project'].create({
            'name': 'Another Project',
            'code': 'ANP',
            'date_start': datetime.date(2025, 1, 1),
            'date_end': datetime.date(2025, 12, 31),
            'state': 'active',
            'manager_id': self.employee.id,
        })
        self.env['agentx.sprint'].create({
            'name': 'Sprint P1',
            'project_id': self.project.id,
            'date_start': datetime.date(2025, 3, 1),
            'date_end': datetime.date(2025, 3, 31),
            'state': 'active',
        })
        sprint2 = self.env['agentx.sprint'].create({
            'name': 'Sprint P2',
            'project_id': project2.id,
            'date_start': datetime.date(2025, 3, 1),
            'date_end': datetime.date(2025, 3, 31),
            'state': 'active',
        })
        self.assertEqual(sprint2.state, 'active')


@tagged('post_install', '-at_install', 'agentx_sprint')
class TestSprintVelocity(TransactionCase):
    """Test velocity is auto-set to completed story points on sprint completion."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env['hr.employee'].create({'name': 'PM Velocity'})
        cls.project = cls.env['agentx.project'].create({
            'name': 'Velocity Project',
            'code': 'VEL',
            'date_start': datetime.date(2025, 1, 1),
            'date_end': datetime.date(2025, 12, 31),
            'state': 'active',
            'manager_id': cls.employee.id,
        })

    def test_velocity_set_to_completed_story_points_on_completion(self):
        sprint = self.env['agentx.sprint'].create({
            'name': 'Velocity Sprint',
            'project_id': self.project.id,
            'date_start': datetime.date(2025, 4, 1),
            'date_end': datetime.date(2025, 4, 30),
            'state': 'active',
        })
        # Add tasks with story points
        self.env['agentx.task'].create({
            'name': 'Done Task 1',
            'project_id': self.project.id,
            'sprint_id': sprint.id,
            'story_points': 5,
            'state': 'done',
        })
        self.env['agentx.task'].create({
            'name': 'Done Task 2',
            'project_id': self.project.id,
            'sprint_id': sprint.id,
            'story_points': 3,
            'state': 'done',
        })
        self.env['agentx.task'].create({
            'name': 'Incomplete Task',
            'project_id': self.project.id,
            'sprint_id': sprint.id,
            'story_points': 8,
            'state': 'in_progress',
        })
        sprint.action_complete()
        self.assertEqual(sprint.state, 'completed')
        # Velocity should equal completed story points (5+3=8)
        self.assertEqual(sprint.velocity, 8)

    def test_velocity_zero_when_no_done_tasks(self):
        sprint = self.env['agentx.sprint'].create({
            'name': 'Zero Velocity Sprint',
            'project_id': self.project.id,
            'date_start': datetime.date(2025, 5, 1),
            'date_end': datetime.date(2025, 5, 31),
            'state': 'active',
        })
        sprint.action_complete()
        self.assertEqual(sprint.velocity, 0)


@tagged('post_install', '-at_install', 'agentx_sprint')
class TestSprintOverdue(TransactionCase):
    """Test is_overdue computed field on agentx.sprint."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env['hr.employee'].create({'name': 'PM Overdue'})
        cls.project = cls.env['agentx.project'].create({
            'name': 'Overdue Project',
            'code': 'OVRD',
            'date_start': datetime.date(2020, 1, 1),
            'manager_id': cls.employee.id,
            'state': 'active',
        })

    def test_active_sprint_past_end_is_overdue(self):
        sprint = self.env['agentx.sprint'].create({
            'name': 'Past Sprint',
            'project_id': self.project.id,
            'date_start': datetime.date(2020, 1, 1),
            'date_end': datetime.date(2020, 1, 31),
            'state': 'active',
        })
        self.assertTrue(sprint.is_overdue)

    def test_active_sprint_with_future_end_not_overdue(self):
        future_end = fields.Date.today() + datetime.timedelta(days=30)
        sprint = self.env['agentx.sprint'].create({
            'name': 'Future Sprint',
            'project_id': self.project.id,
            'date_start': fields.Date.today(),
            'date_end': future_end,
            'state': 'active',
        })
        self.assertFalse(sprint.is_overdue)

    def test_completed_sprint_past_end_not_overdue(self):
        sprint = self.env['agentx.sprint'].create({
            'name': 'Completed Past Sprint',
            'project_id': self.project.id,
            'date_start': datetime.date(2020, 3, 1),
            'date_end': datetime.date(2020, 3, 31),
            'state': 'completed',
        })
        self.assertFalse(sprint.is_overdue)
