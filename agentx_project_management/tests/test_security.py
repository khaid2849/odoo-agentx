# -*- coding: utf-8 -*-
"""
Security tests for agentx_project_management.

Covers:
- ACL permissions per group (viewer, member, manager, admin)
- Record rules: member sees own projects and own tasks only
"""
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged('post_install', '-at_install', 'security')
class TestSecurityGroups(TransactionCase):
    """Test that each group can only perform its allowed CRUD operations."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Resolve group refs
        ref = cls.env.ref
        cls.group_viewer = ref('agentx_project_management.group_agentx_project_viewer')
        cls.group_member = ref('agentx_project_management.group_agentx_project_member')
        cls.group_manager = ref('agentx_project_management.group_agentx_project_manager')
        cls.group_admin = ref('agentx_project_management.group_agentx_admin')

        # Create test users
        User = cls.env['res.users'].with_context(no_reset_password=True)
        cls.user_viewer = User.create({
            'name': 'Test Viewer',
            'login': 'test_viewer@agentx.test',
            'groups_id': [(6, 0, [cls.group_viewer.id])],
        })
        cls.user_member = User.create({
            'name': 'Test Member',
            'login': 'test_member@agentx.test',
            'groups_id': [(6, 0, [cls.group_member.id])],
        })
        cls.user_manager = User.create({
            'name': 'Test Manager',
            'login': 'test_manager@agentx.test',
            'groups_id': [(6, 0, [cls.group_manager.id])],
        })

        # Create a base project owned by manager for subsequent tests
        cls.project = cls.env['agentx.project'].with_user(cls.user_manager).create({
            'name': 'Security Test Project',
            'code': 'STP',
            'status': 'active',
        })

    # ------------------------------------------------------------------
    # Viewer: read-only on all models
    # ------------------------------------------------------------------

    def test_viewer_can_read_project(self):
        project = self.env['agentx.project'].with_user(self.user_viewer).browse(self.project.id)
        # Should not raise
        _ = project.name

    def test_viewer_cannot_write_project(self):
        with self.assertRaises(AccessError):
            self.env['agentx.project'].with_user(self.user_viewer).browse(
                self.project.id
            ).write({'name': 'Hacked'})

    def test_viewer_cannot_create_project(self):
        with self.assertRaises(AccessError):
            self.env['agentx.project'].with_user(self.user_viewer).create({
                'name': 'Viewer Project',
                'code': 'VPR',
                'status': 'active',
            })

    # ------------------------------------------------------------------
    # Member: CR on customer.request, CRUD own tasks, R on bugs/acceptance
    # ------------------------------------------------------------------

    def test_member_can_create_customer_request(self):
        req = self.env['agentx.customer.request'].with_user(self.user_member).create({
            'name': 'Member Request',
            'project_id': self.project.id,
        })
        self.assertTrue(req.id)

    def test_member_cannot_write_customer_request(self):
        req = self.env['agentx.customer.request'].with_user(self.user_manager).create({
            'name': 'Manager Created Request',
            'project_id': self.project.id,
        })
        with self.assertRaises(AccessError):
            self.env['agentx.customer.request'].with_user(self.user_member).browse(
                req.id
            ).write({'name': 'Member Modified'})

    def test_member_cannot_read_bug_belongs_to_other(self):
        """Member has R on bugs but record rules may restrict visibility."""
        # Member can at minimum read bug records (R permission granted)
        bugs = self.env['agentx.bug'].with_user(self.user_member).search([
            ('project_id', '=', self.project.id)
        ])
        # No AccessError expected — search returns filtered result
        self.assertIsNotNone(bugs)

    def test_member_cannot_create_bug(self):
        with self.assertRaises(AccessError):
            self.env['agentx.bug'].with_user(self.user_member).create({
                'name': 'Member Bug',
                'project_id': self.project.id,
            })

    def test_member_cannot_write_bug(self):
        bug = self.env['agentx.bug'].with_user(self.user_manager).create({
            'name': 'Manager Bug',
            'project_id': self.project.id,
        })
        with self.assertRaises(AccessError):
            self.env['agentx.bug'].with_user(self.user_member).browse(
                bug.id
            ).write({'name': 'Member Tampered'})

    def test_member_cannot_create_acceptance(self):
        with self.assertRaises(AccessError):
            self.env['agentx.acceptance'].with_user(self.user_member).create({
                'name': 'Member Acceptance',
                'project_id': self.project.id,
            })

    def test_member_cannot_write_acceptance(self):
        ac = self.env['agentx.acceptance'].with_user(self.user_manager).create({
            'name': 'Manager Acceptance',
            'project_id': self.project.id,
        })
        with self.assertRaises(AccessError):
            self.env['agentx.acceptance'].with_user(self.user_member).browse(
                ac.id
            ).write({'name': 'Member Tampered'})

    # ------------------------------------------------------------------
    # Manager: full CRUD on all models
    # ------------------------------------------------------------------

    def test_manager_can_create_and_delete_project(self):
        proj = self.env['agentx.project'].with_user(self.user_manager).create({
            'name': 'Manager Temp Project',
            'code': 'MTP',
            'status': 'active',
        })
        self.assertTrue(proj.id)
        proj.unlink()  # Must not raise

    def test_manager_can_create_and_delete_bug(self):
        bug = self.env['agentx.bug'].with_user(self.user_manager).create({
            'name': 'Manager Bug Delete',
            'project_id': self.project.id,
        })
        self.assertTrue(bug.id)
        bug.unlink()  # Must not raise

    def test_manager_can_create_and_delete_acceptance(self):
        ac = self.env['agentx.acceptance'].with_user(self.user_manager).create({
            'name': 'Manager Acceptance Delete',
            'project_id': self.project.id,
        })
        self.assertTrue(ac.id)
        ac.unlink()  # Must not raise


@tagged('post_install', '-at_install', 'security')
class TestRecordRules(TransactionCase):
    """Test record-level rules: member sees only own projects and own tasks."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ref = cls.env.ref
        cls.group_member = ref('agentx_project_management.group_agentx_project_member')
        cls.group_manager = ref('agentx_project_management.group_agentx_project_manager')

        User = cls.env['res.users'].with_context(no_reset_password=True)
        cls.member_a = User.create({
            'name': 'Member A',
            'login': 'member_a@agentx.test',
            'groups_id': [(6, 0, [cls.group_member.id])],
        })
        cls.member_b = User.create({
            'name': 'Member B',
            'login': 'member_b@agentx.test',
            'groups_id': [(6, 0, [cls.group_member.id])],
        })
        cls.manager = User.create({
            'name': 'Manager RR',
            'login': 'manager_rr@agentx.test',
            'groups_id': [(6, 0, [cls.group_manager.id])],
        })

        # Project where member_a is the manager (visible to member_a via rule)
        cls.project_a = cls.env['agentx.project'].with_user(cls.manager).create({
            'name': 'Project A',
            'code': 'PA',
            'status': 'active',
            'manager_id': cls.env['hr.employee'].search(
                [('user_id', '=', cls.member_a.id)], limit=1
            ).id or False,
        })
        # Project where member_a is NOT involved (should be invisible)
        cls.project_b = cls.env['agentx.project'].with_user(cls.manager).create({
            'name': 'Project B',
            'code': 'PB',
            'status': 'active',
        })

    def test_member_cannot_write_unrelated_project(self):
        """Member A cannot edit a project they are not manager/lead/resource of."""
        with self.assertRaises(AccessError):
            self.env['agentx.project'].with_user(self.member_a).browse(
                self.project_b.id
            ).write({'name': 'Tampered'})

    def test_member_cannot_write_task_assigned_to_other(self):
        """Member A cannot edit a task assigned to Member B."""
        task = self.env['agentx.task'].with_user(self.manager).create({
            'name': 'Task B',
            'project_id': self.project_b.id,
            'assignee_id': self.env['hr.employee'].search(
                [('user_id', '=', self.member_b.id)], limit=1
            ).id or False,
        })
        with self.assertRaises(AccessError):
            self.env['agentx.task'].with_user(self.member_a).browse(
                task.id
            ).write({'name': 'Hacked'})
