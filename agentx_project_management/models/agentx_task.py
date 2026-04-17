# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class AgentxTag(models.Model):
    _name = 'agentx.tag'
    _description = 'AgentX Tag'
    _order = 'name'

    name = fields.Char(string='Tag Name', required=True)
    color = fields.Integer(string='Color Index')

    _sql_constraints = [
        ('name_uniq', 'UNIQUE(name)', 'Tag name must be unique!'),
    ]


class AgentxTask(models.Model):
    _name = 'agentx.task'
    _description = 'AgentX Task'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, sequence, id desc'
    _rec_name = 'name'

    # ── Core fields ───────────────────────────────────────────────────────────
    name = fields.Char(
        string='Task Title',
        required=True,
        tracking=True,
    )
    code = fields.Char(
        string='Task Code',
        readonly=True,
        copy=False,
        index=True,
    )
    task_type = fields.Selection(
        selection=[
            ('story', 'User Story'),
            ('task', 'Task'),
            ('improvement', 'Improvement'),
        ],
        string='Type',
        default='task',
        required=True,
        tracking=True,
    )
    state = fields.Selection(
        selection=[
            ('backlog', 'Backlog'),
            ('todo', 'To Do'),
            ('in_progress', 'In Progress'),
            ('blocked', 'Blocked'),
            ('done', 'Done'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='backlog',
        required=True,
        tracking=True,
    )
    priority = fields.Selection(
        selection=[
            ('0', 'Normal'),
            ('1', 'Medium'),
            ('2', 'High'),
            ('3', 'Critical'),
        ],
        string='Priority',
        default='0',
        tracking=True,
    )
    sequence = fields.Integer(string='Sequence', default=10)
    description = fields.Html(string='Description')
    acceptance_criteria = fields.Text(string='Acceptance Criteria')
    block_reason = fields.Text(string='Block Reason')

    # ── Project / Sprint ──────────────────────────────────────────────────────
    project_id = fields.Many2one(
        comodel_name='agentx.project',
        string='Project',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True,
    )
    sprint_id = fields.Many2one(
        comodel_name='agentx.sprint',
        string='Sprint',
        tracking=True,
        domain="[('project_id', '=', project_id), ('state', 'in', ['draft', 'active'])]",
    )

    # ── People ────────────────────────────────────────────────────────────────
    assignee_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Assignee',
        tracking=True,
        index=True,
    )
    reviewer_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Reviewer',
    )

    # ── Estimates ─────────────────────────────────────────────────────────────
    story_points = fields.Integer(
        string='Story Points',
        help='Relative effort estimate.',
    )
    estimated_hours = fields.Float(
        string='Estimated Hours',
        digits=(6, 2),
    )

    # ── Dates ─────────────────────────────────────────────────────────────────
    date_deadline = fields.Date(string='Deadline', tracking=True)
    date_started = fields.Datetime(string='Date Started', readonly=True)
    date_done = fields.Datetime(string='Date Done', readonly=True)

    # ── Tags & timesheets ─────────────────────────────────────────────────────
    tag_ids = fields.Many2many(
        comodel_name='agentx.tag',
        string='Tags',
    )
    timesheet_ids = fields.One2many(
        comodel_name='account.analytic.line',
        inverse_name='agentx_task_id',
        string='Timesheets',
    )
    actual_hours = fields.Float(
        compute='_compute_actual_hours',
        string='Actual Hours',
        store=True,
        digits=(6, 2),
    )

    # ── Compute methods ───────────────────────────────────────────────────────
    @api.depends('timesheet_ids.unit_amount')
    def _compute_actual_hours(self):
        for task in self:
            task.actual_hours = sum(task.timesheet_ids.mapped('unit_amount'))

    # ── ORM overrides ─────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = (
                    self.env['ir.sequence'].next_by_code('agentx.task') or '/'
                )
        return super().create(vals_list)

    # ── Constraints ───────────────────────────────────────────────────────────
    @api.constrains('sprint_id', 'project_id')
    def _check_sprint_project(self):
        for task in self:
            if task.sprint_id and task.sprint_id.project_id != task.project_id:
                raise ValidationError(
                    _("Sprint '%s' does not belong to project '%s'.")
                    % (task.sprint_id.name, task.project_id.name)
                )

    # ── State machine actions ─────────────────────────────────────────────────
    def action_plan(self):
        """Transition Backlog → To Do (add to sprint)."""
        for task in self:
            if task.state != 'backlog':
                raise UserError(_("Only backlog tasks can be planned."))
            task.state = 'todo'
            task.message_post(body=_("Task moved to sprint backlog."))

    def action_start(self):
        """Transition To Do → In Progress."""
        for task in self:
            if task.state not in ('todo', 'blocked'):
                raise UserError(_("Only planned or blocked tasks can be started."))
            task.write({
                'state': 'in_progress',
                'date_started': fields.Datetime.now(),
            })
            task.message_post(body=_("Task started."))

    def action_block(self):
        """Transition In Progress → Blocked."""
        for task in self:
            if task.state != 'in_progress':
                raise UserError(_("Only in-progress tasks can be blocked."))
            task.state = 'blocked'
            task.message_post(body=_("Task blocked. Reason: %s") % (task.block_reason or ''))

    def action_unblock(self):
        """Transition Blocked → In Progress."""
        for task in self:
            if task.state != 'blocked':
                raise UserError(_("Only blocked tasks can be unblocked."))
            task.write({
                'state': 'in_progress',
                'block_reason': False,
            })
            task.message_post(body=_("Task unblocked."))

    def action_done(self):
        """Transition In Progress → Done."""
        for task in self:
            if task.state not in ('in_progress', 'todo'):
                raise UserError(_("Only in-progress or planned tasks can be marked as done."))
            task.write({
                'state': 'done',
                'date_done': fields.Datetime.now(),
            })
            task.message_post(body=_("Task completed."))

    def action_cancel(self):
        """Transition any open state → Cancelled."""
        for task in self:
            if task.state in ('done', 'cancelled'):
                raise UserError(_("Completed or already cancelled tasks cannot be cancelled."))
            task.state = 'cancelled'
            task.message_post(body=_("Task cancelled."))

    def action_reopen(self):
        """Transition Done/Cancelled → Backlog."""
        for task in self:
            if task.state not in ('done', 'cancelled'):
                raise UserError(_("Only done or cancelled tasks can be reopened."))
            task.write({
                'state': 'backlog',
                'date_done': False,
            })
            task.message_post(body=_("Task reopened."))
