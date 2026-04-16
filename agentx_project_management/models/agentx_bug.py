# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class AgentxBug(models.Model):
    _name = 'agentx.bug'
    _description = 'AgentX Bug'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, id desc'
    _rec_name = 'name'

    # ── Core fields ───────────────────────────────────────────────────────────
    name = fields.Char(
        string='Bug Title',
        required=True,
        tracking=True,
    )
    code = fields.Char(
        string='Bug Code',
        readonly=True,
        copy=False,
        index=True,
    )
    state = fields.Selection(
        selection=[
            ('new', 'New'),
            ('confirmed', 'Confirmed'),
            ('in_progress', 'In Progress'),
            ('resolved', 'Resolved'),
            ('closed', 'Closed'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='new',
        required=True,
        tracking=True,
    )
    priority = fields.Selection(
        selection=[
            ('0', 'Low'),
            ('1', 'Normal'),
            ('2', 'High'),
            ('3', 'Critical'),
        ],
        string='Priority',
        default='1',
        tracking=True,
    )
    severity = fields.Selection(
        selection=[
            ('minor', 'Minor'),
            ('major', 'Major'),
            ('critical', 'Critical'),
            ('blocker', 'Blocker'),
        ],
        string='Severity',
        default='major',
        required=True,
        tracking=True,
    )

    # ── Project / Sprint / Task ────────────────────────────────────────────────
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
        domain="[('project_id', '=', project_id)]",
    )
    related_task_id = fields.Many2one(
        comodel_name='agentx.task',
        string='Related Task',
        domain="[('project_id', '=', project_id)]",
    )

    # ── People ────────────────────────────────────────────────────────────────
    reported_by = fields.Many2one(
        comodel_name='res.partner',
        string='Reported By',
    )
    assignee_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Assignee',
        tracking=True,
        index=True,
    )

    # ── Bug details ───────────────────────────────────────────────────────────
    description = fields.Html(string='Description')
    steps_to_reproduce = fields.Text(string='Steps to Reproduce')
    expected_behavior = fields.Text(string='Expected Behavior')
    actual_behavior = fields.Text(string='Actual Behavior')
    environment = fields.Char(
        string='Environment',
        help='e.g. Production, Staging, v18.0.1',
    )

    # ── Dates ─────────────────────────────────────────────────────────────────
    date_reported = fields.Date(
        string='Date Reported',
        default=fields.Date.today,
        required=True,
    )
    date_confirmed = fields.Date(string='Date Confirmed', readonly=True)
    date_resolved = fields.Date(string='Date Resolved', tracking=True, readonly=True)
    date_closed = fields.Date(string='Date Closed', readonly=True)

    # ── Resolution ────────────────────────────────────────────────────────────
    resolution = fields.Text(string='Resolution Notes')

    # ── ORM overrides ─────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = (
                    self.env['ir.sequence'].next_by_code('agentx.bug') or '/'
                )
        return super().create(vals_list)

    # ── Constraints ───────────────────────────────────────────────────────────
    @api.constrains('sprint_id', 'project_id')
    def _check_sprint_project(self):
        for bug in self:
            if bug.sprint_id and bug.sprint_id.project_id != bug.project_id:
                raise ValidationError(
                    _("Sprint '%s' does not belong to project '%s'.")
                    % (bug.sprint_id.name, bug.project_id.name)
                )

    # ── State machine actions ─────────────────────────────────────────────────
    def action_confirm(self):
        """Transition New → Confirmed."""
        for bug in self:
            if bug.state != 'new':
                raise UserError(_("Only new bugs can be confirmed."))
            bug.write({
                'state': 'confirmed',
                'date_confirmed': fields.Date.today(),
            })
            bug.message_post(body=_("Bug confirmed."))

    def action_start_fix(self):
        """Transition Confirmed → In Progress."""
        for bug in self:
            if bug.state != 'confirmed':
                raise UserError(_("Only confirmed bugs can be assigned for fixing."))
            bug.state = 'in_progress'
            bug.message_post(body=_("Bug fix started."))

    def action_resolve(self):
        """Transition In Progress → Resolved."""
        for bug in self:
            if bug.state != 'in_progress':
                raise UserError(_("Only in-progress bugs can be resolved."))
            bug.write({
                'state': 'resolved',
                'date_resolved': fields.Date.today(),
            })
            bug.message_post(
                body=_("Bug resolved. Resolution: %s") % (bug.resolution or _("No notes."))
            )

    def action_close(self):
        """Transition Resolved → Closed."""
        for bug in self:
            if bug.state != 'resolved':
                raise UserError(_("Only resolved bugs can be closed."))
            bug.write({
                'state': 'closed',
                'date_closed': fields.Date.today(),
            })
            bug.message_post(body=_("Bug closed."))

    def action_reopen(self):
        """Transition Resolved → Confirmed (regression)."""
        for bug in self:
            if bug.state != 'resolved':
                raise UserError(_("Only resolved bugs can be reopened."))
            bug.write({
                'state': 'confirmed',
                'date_resolved': False,
            })
            bug.message_post(body=_("Bug reopened (regression detected)."))

    def action_cancel(self):
        """Transition any open state → Cancelled."""
        for bug in self:
            if bug.state in ('closed', 'cancelled'):
                raise UserError(_("Closed or already cancelled bugs cannot be cancelled."))
            bug.state = 'cancelled'
            bug.message_post(body=_("Bug cancelled."))
