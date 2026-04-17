# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class AgentxProject(models.Model):
    _name = 'agentx.project'
    _description = 'AgentX Project'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc, id desc'
    _rec_name = 'name'

    # ── Core fields ──────────────────────────────────────────────────────────
    name = fields.Char(
        string='Project Name',
        required=True,
        tracking=True,
    )
    code = fields.Char(
        string='Project Code',
        required=True,
        copy=False,
        tracking=True,
    )
    description = fields.Html(string='Description')
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('in_progress', 'In Progress'),
            ('done', 'Done'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
    )
    priority = fields.Selection(
        selection=[
            ('0', 'Normal'),
            ('1', 'High'),
            ('2', 'Critical'),
        ],
        string='Priority',
        default='0',
        tracking=True,
    )

    # ── Dates ─────────────────────────────────────────────────────────────────
    date_start = fields.Date(
        string='Start Date',
        required=True,
        tracking=True,
    )
    date_end = fields.Date(
        string='End Date',
        tracking=True,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    manager_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Project Manager',
        required=True,
        tracking=True,
        index=True,
    )
    customer_id = fields.Many2one(
        comodel_name='res.partner',
        string='Customer',
        tracking=True,
    )
    team_ids = fields.One2many(
        comodel_name='agentx.team.member',
        inverse_name='project_id',
        string='Team Members',
    )
    sprint_ids = fields.One2many(
        comodel_name='agentx.sprint',
        inverse_name='project_id',
        string='Sprints',
    )
    task_ids = fields.One2many(
        comodel_name='agentx.task',
        inverse_name='project_id',
        string='Tasks',
    )
    bug_ids = fields.One2many(
        comodel_name='agentx.bug',
        inverse_name='project_id',
        string='Bugs',
    )
    milestone_ids = fields.One2many(
        comodel_name='agentx.milestone',
        inverse_name='project_id',
        string='Milestones',
    )
    acceptance_ids = fields.One2many(
        comodel_name='agentx.acceptance',
        inverse_name='project_id',
        string='Acceptance Criteria',
    )

    # ── Computed / stat buttons ───────────────────────────────────────────────
    sprint_count = fields.Integer(
        compute='_compute_sprint_count',
        string='Sprints',
    )
    task_count = fields.Integer(
        compute='_compute_task_count',
        string='Tasks',
    )
    bug_count = fields.Integer(
        compute='_compute_bug_count',
        string='Bugs',
    )
    open_bug_count = fields.Integer(
        compute='_compute_bug_count',
        string='Open Bugs',
    )
    completion_rate = fields.Float(
        compute='_compute_completion_rate',
        string='Completion (%)',
        digits=(5, 2),
    )

    # ── SQL Constraints ───────────────────────────────────────────────────────
    _sql_constraints = [
        ('code_uniq', 'UNIQUE(code)', 'Project code must be unique!'),
    ]

    # ── Compute methods ───────────────────────────────────────────────────────
    @api.depends('sprint_ids')
    def _compute_sprint_count(self):
        for project in self:
            project.sprint_count = len(project.sprint_ids)

    @api.depends('task_ids')
    def _compute_task_count(self):
        for project in self:
            project.task_count = len(project.task_ids)

    @api.depends('bug_ids', 'bug_ids.state')
    def _compute_bug_count(self):
        for project in self:
            project.bug_count = len(project.bug_ids)
            project.open_bug_count = len(
                project.bug_ids.filtered(
                    lambda b: b.state not in ('closed', 'cancelled')
                )
            )

    @api.depends('task_ids', 'task_ids.state')
    def _compute_completion_rate(self):
        for project in self:
            total = len(project.task_ids)
            if total:
                done = len(project.task_ids.filtered(lambda t: t.state == 'done'))
                project.completion_rate = (done / total) * 100.0
            else:
                project.completion_rate = 0.0

    # ── Constraints ───────────────────────────────────────────────────────────
    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for project in self:
            if project.date_end and project.date_start and project.date_end < project.date_start:
                raise ValidationError(_("Project end date cannot be before start date."))

    # ── State machine actions ─────────────────────────────────────────────────
    def action_start(self):
        """Transition Draft → In Progress."""
        for project in self:
            if project.state != 'draft':
                raise UserError(_("Only draft projects can be started."))
            project.state = 'in_progress'
            project.message_post(body=_("Project started."))

    def action_done(self):
        """Transition In Progress → Done."""
        for project in self:
            if project.state != 'in_progress':
                raise UserError(_("Only in-progress projects can be closed."))
            open_bugs = project.bug_ids.filtered(lambda b: b.state not in ('closed', 'cancelled'))
            if open_bugs:
                raise UserError(
                    _("Cannot close project with %d open bug(s). Please resolve or cancel them first.")
                    % len(open_bugs)
                )
            project.state = 'done'
            project.message_post(body=_("Project closed successfully."))

    def action_cancel(self):
        """Transition In Progress → Cancelled."""
        for project in self:
            if project.state not in ('draft', 'in_progress'):
                raise UserError(_("Only draft or in-progress projects can be cancelled."))
            project.state = 'cancelled'
            project.message_post(body=_("Project cancelled."))

    def action_reset_to_draft(self):
        """Transition Cancelled → Draft."""
        for project in self:
            if project.state != 'cancelled':
                raise UserError(_("Only cancelled projects can be reset to draft."))
            project.state = 'draft'
            project.message_post(body=_("Project reset to draft."))

    # ── Smart button actions ──────────────────────────────────────────────────
    def action_view_sprints(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sprints'),
            'res_model': 'agentx.sprint',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_view_tasks(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tasks'),
            'res_model': 'agentx.task',
            'view_mode': 'list,kanban,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_view_bugs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bugs'),
            'res_model': 'agentx.bug',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }
