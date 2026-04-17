# -*- coding: utf-8 -*-
"""
Unit tests for agentx.bug model.

Covers:
- State machine transitions (new → confirmed → in_progress → resolved → closed)
- Reopen path (resolved → confirmed)
- Cancel from open states
- Code auto-generation via ir.sequence
"""
import datetime

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged('post_install', '-at_install', 'agentx_bug')
class TestBugStateMachine(TransactionCase):
    """Test state machine transitions on agentx.bug."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env['hr.employee'].create({'name': 'PM Bug SM'})
        cls.project = cls.env['agentx.project'].create({
            'name': 'Bug SM Project',
            'code': 'BSM',
            'date_start': datetime.date(2025, 1, 1),
            'manager_id': cls.employee.id,
            'state': 'active',
        })

    def _make_bug(self, state='new'):
        bug = self.env['agentx.bug'].create({
            'name': 'Test Bug',
            'project_id': self.project.id,
        })
        if state != 'new':
            bug.write({'state': state})
        return bug

    # ------------------------------------------------------------------
    # new → confirmed
    # ------------------------------------------------------------------
    def test_action_confirm_from_new(self):
        bug = self._make_bug()
        bug.action_confirm()
        self.assertEqual(bug.state, 'confirmed')
        self.assertTrue(bug.date_confirmed)

    def test_action_confirm_sets_date_confirmed(self):
        bug = self._make_bug()
        bug.action_confirm()
        self.assertEqual(bug.date_confirmed, fields.Date.today())

    def test_action_confirm_not_from_new_raises(self):
        bug = self._make_bug(state='confirmed')
        with self.assertRaises(UserError):
            bug.action_confirm()

    # ------------------------------------------------------------------
    # confirmed → in_progress
    # ------------------------------------------------------------------
    def test_action_start_fix_from_confirmed(self):
        bug = self._make_bug(state='confirmed')
        bug.action_start_fix()
        self.assertEqual(bug.state, 'in_progress')

    def test_action_start_fix_not_from_confirmed_raises(self):
        bug = self._make_bug()
        with self.assertRaises(UserError):
            bug.action_start_fix()

    # ------------------------------------------------------------------
    # in_progress → resolved
    # ------------------------------------------------------------------
    def test_action_resolve_from_in_progress(self):
        bug = self._make_bug(state='in_progress')
        bug.action_resolve()
        self.assertEqual(bug.state, 'resolved')
        self.assertTrue(bug.date_resolved)

    def test_action_resolve_sets_date_resolved(self):
        bug = self._make_bug(state='in_progress')
        bug.action_resolve()
        self.assertEqual(bug.date_resolved, fields.Date.today())

    def test_action_resolve_not_from_in_progress_raises(self):
        bug = self._make_bug(state='confirmed')
        with self.assertRaises(UserError):
            bug.action_resolve()

    # ------------------------------------------------------------------
    # resolved → closed
    # ------------------------------------------------------------------
    def test_action_close_from_resolved(self):
        bug = self._make_bug(state='resolved')
        bug.action_close()
        self.assertEqual(bug.state, 'closed')
        self.assertTrue(bug.date_closed)

    def test_action_close_sets_date_closed(self):
        bug = self._make_bug(state='resolved')
        bug.action_close()
        self.assertEqual(bug.date_closed, fields.Date.today())

    def test_action_close_not_from_resolved_raises(self):
        bug = self._make_bug(state='in_progress')
        with self.assertRaises(UserError):
            bug.action_close()

    # ------------------------------------------------------------------
    # resolved → confirmed (reopen / regression)
    # ------------------------------------------------------------------
    def test_action_reopen_from_resolved(self):
        bug = self._make_bug(state='resolved')
        bug.action_reopen()
        self.assertEqual(bug.state, 'confirmed')
        self.assertFalse(bug.date_resolved)

    def test_action_reopen_not_from_resolved_raises(self):
        bug = self._make_bug(state='in_progress')
        with self.assertRaises(UserError):
            bug.action_reopen()

    # ------------------------------------------------------------------
    # any open state → cancelled
    # ------------------------------------------------------------------
    def test_action_cancel_from_new(self):
        bug = self._make_bug()
        bug.action_cancel()
        self.assertEqual(bug.state, 'cancelled')

    def test_action_cancel_from_confirmed(self):
        bug = self._make_bug(state='confirmed')
        bug.action_cancel()
        self.assertEqual(bug.state, 'cancelled')

    def test_action_cancel_from_in_progress(self):
        bug = self._make_bug(state='in_progress')
        bug.action_cancel()
        self.assertEqual(bug.state, 'cancelled')

    def test_action_cancel_from_resolved(self):
        bug = self._make_bug(state='resolved')
        bug.action_cancel()
        self.assertEqual(bug.state, 'cancelled')

    def test_action_cancel_from_closed_raises(self):
        bug = self._make_bug(state='closed')
        with self.assertRaises(UserError):
            bug.action_cancel()

    def test_action_cancel_from_cancelled_raises(self):
        bug = self._make_bug(state='cancelled')
        with self.assertRaises(UserError):
            bug.action_cancel()


@tagged('post_install', '-at_install', 'agentx_bug')
class TestBugCodeAutoGeneration(TransactionCase):
    """Test that agentx.bug.code is auto-generated via ir.sequence."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env['hr.employee'].create({'name': 'PM Bug Code'})
        cls.project = cls.env['agentx.project'].create({
            'name': 'Bug Code Project',
            'code': 'BCP',
            'date_start': datetime.date.today(),
            'manager_id': cls.employee.id,
        })

    def test_bug_code_is_generated_on_create(self):
        bug = self.env['agentx.bug'].create({
            'name': 'Code Auto Bug',
            'project_id': self.project.id,
        })
        self.assertTrue(bug.code)
        self.assertNotEqual(bug.code, '/')

    def test_bug_code_starts_with_bug_prefix(self):
        bug = self.env['agentx.bug'].create({
            'name': 'Bug Prefix Check',
            'project_id': self.project.id,
        })
        self.assertTrue(bug.code.startswith('BUG-'))

    def test_bug_codes_are_unique(self):
        bug1 = self.env['agentx.bug'].create({
            'name': 'Bug One',
            'project_id': self.project.id,
        })
        bug2 = self.env['agentx.bug'].create({
            'name': 'Bug Two',
            'project_id': self.project.id,
        })
        self.assertNotEqual(bug1.code, bug2.code)
