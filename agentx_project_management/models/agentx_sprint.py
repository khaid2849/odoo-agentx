# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class AgentxSprint(models.Model):
    _name = 'agentx.sprint'
    _description = 'AgentX Sprint'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'project_id, sequence, id'
    _rec_name = 'name'

    # ── Core fields ───────────────────────────────────────────────────────────
    name = fields.Char(
        string='Sprint Name',
        required=True,
        tracking=True,
    )
    project_id = fields.Many2one(
        comodel_name='agentx.project',
        string='Project',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True,
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    state = fields.Selection(
        selection=[
            ('planning', 'Planning'),
            ('active', 'Active'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='planning',
        required=True,
        tracking=True,
    )
    goal = fields.Text(string='Sprint Goal')

    # ── Dates ─────────────────────────────────────────────────────────────────
    date_start = fields.Date(
        string='Start Date',
        required=True,
        tracking=True,
    )
    date_end = fields.Date(
        string='End Date',
        required=True,
        tracking=True,
    )

    # ── Capacity ──────────────────────────────────────────────────────────────
    velocity = fields.Integer(
        string='Velocity (Story Points)',
        help='Actual story points completed in this sprint.',
    )
    capacity = fields.Integer(
        string='Capacity (Story Points)',
        help='Planned story points capacity for this sprint.',
    )

    # ── Tasks ─────────────────────────────────────────────────────────────────
    task_ids = fields.One2many(
        comodel_name='agentx.task',
        inverse_name='sprint_id',
        string='Tasks',
    )

    # ── Computed ──────────────────────────────────────────────────────────────
    task_count = fields.Integer(
        compute='_compute_task_stats',
        string='Total Tasks',
        store=True,
    )
    done_task_count = fields.Integer(
        compute='_compute_task_stats',
        string='Done Tasks',
        store=True,
    )
    completion_rate = fields.Float(
        compute='_compute_task_stats',
        string='Completion (%)',
        store=True,
        digits=(5, 2),
    )
    total_story_points = fields.Integer(
        compute='_compute_task_stats',
        string='Total Story Points',
        store=True,
    )
    completed_story_points = fields.Integer(
        compute='_compute_task_stats',
        string='Completed Story Points',
        store=True,
        help='Sum of story points for tasks in Done state.',
    )
    progress_pct = fields.Float(
        compute='_compute_task_stats',
        string='Progress (%)',
        store=True,
        digits=(5, 2),
        help='Percentage of story points completed vs total.',
    )
    is_overdue = fields.Boolean(
        compute='_compute_is_overdue',
        string='Overdue',
    )

    # ── Constraints ───────────────────────────────────────────────────────────
    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for sprint in self:
            if sprint.date_end and sprint.date_start and sprint.date_end < sprint.date_start:
                raise ValidationError(_("Sprint end date cannot be before start date."))

    @api.constrains('date_start', 'date_end', 'project_id')
    def _check_dates_within_project(self):
        """CHK-03: Sprint dates must fall within the project date range."""
        for sprint in self:
            proj = sprint.project_id
            if not proj:
                continue
            if proj.date_start and sprint.date_start and sprint.date_start < proj.date_start:
                raise ValidationError(
                    _("Sprint '%s' start date cannot be before project start date (%s).")
                    % (sprint.name, proj.date_start)
                )
            if proj.date_end and sprint.date_end and sprint.date_end > proj.date_end:
                raise ValidationError(
                    _("Sprint '%s' end date cannot be after project end date (%s).")
                    % (sprint.name, proj.date_end)
                )

    @api.constrains('project_id', 'state')
    def _check_one_active_sprint(self):
        for sprint in self:
            if sprint.state == 'active':
                others = self.search([
                    ('project_id', '=', sprint.project_id.id),
                    ('state', '=', 'active'),
                    ('id', '!=', sprint.id),
                ])
                if others:
                    raise ValidationError(
                        _("Project '%s' already has an active sprint. "
                          "Complete or cancel it before starting a new one.")
                        % sprint.project_id.name
                    )

    # ── Compute methods ───────────────────────────────────────────────────────
    @api.depends('task_ids', 'task_ids.state', 'task_ids.story_points')
    def _compute_task_stats(self):
        for sprint in self:
            tasks = sprint.task_ids
            done_tasks = tasks.filtered(lambda t: t.state == 'done')
            total = len(tasks)
            done = len(done_tasks)
            sprint.task_count = total
            sprint.done_task_count = done
            sprint.completion_rate = (done / total * 100.0) if total else 0.0
            sprint.total_story_points = sum(tasks.mapped('story_points'))
            sprint.completed_story_points = sum(done_tasks.mapped('story_points'))
            total_pts = sprint.total_story_points
            sprint.progress_pct = (
                (sprint.completed_story_points / total_pts * 100.0)
                if total_pts else 0.0
            )

    def _compute_is_overdue(self):
        today = fields.Date.today()
        for sprint in self:
            sprint.is_overdue = (
                sprint.state == 'active'
                and sprint.date_end
                and sprint.date_end < today
            )

    # ── State machine actions ─────────────────────────────────────────────────
    def action_start(self):
        """Transition Planning → Active."""
        for sprint in self:
            if sprint.state != 'planning':
                raise UserError(_("Only planned sprints can be started."))
            if sprint.project_id.state != 'active':
                raise UserError(
                    _("Cannot start a sprint on a project that is not active.")
                )
            sprint.state = 'active'
            sprint.message_post(body=_("Sprint started: %s") % sprint.name)
            _logger.info("Sprint %s (id=%s) started.", sprint.name, sprint.id)

    def action_complete(self):
        """Transition Active → Completed."""
        for sprint in self:
            if sprint.state != 'active':
                raise UserError(_("Only active sprints can be completed."))
            in_progress_tasks = sprint.task_ids.filtered(
                lambda t: t.state == 'in_progress'
            )
            if in_progress_tasks:
                _logger.warning(
                    "Sprint %s completed with %d in-progress task(s).",
                    sprint.name, len(in_progress_tasks),
                )
            sprint.velocity = sprint.total_story_points if sprint.done_task_count else 0
            sprint.state = 'completed'
            sprint.message_post(
                body=_("Sprint completed. Velocity: %d story points.") % sprint.velocity
            )

    def action_cancel(self):
        """Transition Planning/Active → Cancelled."""
        for sprint in self:
            if sprint.state not in ('planning', 'active'):
                raise UserError(_("Only planned or active sprints can be cancelled."))
            sprint.state = 'cancelled'
            sprint.message_post(body=_("Sprint cancelled."))

    def action_reset_to_planning(self):
        """Transition Cancelled → Planning."""
        for sprint in self:
            if sprint.state != 'cancelled':
                raise UserError(_("Only cancelled sprints can be reset to planning."))
            sprint.state = 'planning'
            sprint.message_post(body=_("Sprint reset to planning."))

    # ── Scheduled action helper ───────────────────────────────────────────────
    @api.model
    def _cron_notify_overdue_sprints(self):
        """Cron job: post a chatter message on active sprints past their end date."""
        today = fields.Date.today()
        overdue = self.search([
            ('state', '=', 'active'),
            ('date_end', '<', today),
        ])
        for sprint in overdue:
            sprint.message_post(
                body=_("⚠️ Sprint '%s' is overdue (deadline: %s). "
                       "Please complete or extend the sprint.")
                % (sprint.name, sprint.date_end),
            )
        if overdue:
            _logger.info("Cron: notified %d overdue active sprint(s).", len(overdue))
