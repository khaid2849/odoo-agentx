# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AgentxMilestone(models.Model):
    _name = 'agentx.milestone'
    _description = 'AgentX Milestone'
    _inherit = ['mail.thread']
    _order = 'project_id, date_deadline'
    _rec_name = 'name'

    name = fields.Char(
        string='Milestone',
        required=True,
        tracking=True,
    )
    project_id = fields.Many2one(
        comodel_name='agentx.project',
        string='Project',
        required=True,
        ondelete='cascade',
        index=True,
    )
    date_deadline = fields.Date(
        string='Deadline',
        required=True,
        tracking=True,
    )
    state = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('achieved', 'Achieved'),
            ('missed', 'Missed'),
        ],
        string='Status',
        default='pending',
        required=True,
        tracking=True,
    )
    description = fields.Text(string='Description')
    responsible_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Responsible',
    )
    is_overdue = fields.Boolean(
        compute='_compute_is_overdue',
        string='Overdue',
        store=True,
    )

    # ── Compute ───────────────────────────────────────────────────────────────
    @api.depends('state', 'date_deadline')
    def _compute_is_overdue(self):
        today = fields.Date.today()
        for milestone in self:
            milestone.is_overdue = (
                milestone.state == 'pending'
                and milestone.date_deadline
                and milestone.date_deadline < today
            )

    # ── State machine actions ─────────────────────────────────────────────────
    def action_achieve(self):
        """Mark milestone as achieved."""
        for milestone in self:
            if milestone.state != 'pending':
                raise UserError(_("Only pending milestones can be marked as achieved."))
            milestone.state = 'achieved'
            milestone.message_post(body=_("Milestone achieved: %s") % milestone.name)

    def action_miss(self):
        """Mark milestone as missed."""
        for milestone in self:
            if milestone.state != 'pending':
                raise UserError(_("Only pending milestones can be marked as missed."))
            milestone.state = 'missed'
            milestone.message_post(body=_("Milestone missed: %s") % milestone.name)

    def action_reopen(self):
        """Re-open a missed milestone."""
        for milestone in self:
            if milestone.state != 'missed':
                raise UserError(_("Only missed milestones can be reopened."))
            milestone.state = 'pending'
            milestone.message_post(body=_("Milestone reopened."))

    # ── Scheduled action helper ───────────────────────────────────────────────
    @api.model
    def _cron_flag_overdue_milestones(self):
        """Cron job: automatically flag overdue pending milestones as missed."""
        today = fields.Date.today()
        overdue = self.search([
            ('state', '=', 'pending'),
            ('date_deadline', '<', today),
        ])
        if overdue:
            overdue.write({'state': 'missed'})
            for milestone in overdue:
                milestone.message_post(
                    body=_("Milestone automatically flagged as missed (deadline passed).")
                )
            _logger.info("Cron: flagged %d overdue milestone(s) as missed.", len(overdue))
