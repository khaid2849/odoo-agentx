# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AgentxAcceptanceLine(models.Model):
    _name = 'agentx.acceptance.line'
    _description = 'AgentX Acceptance Criteria Line'
    _order = 'acceptance_id, sequence'

    acceptance_id = fields.Many2one(
        comodel_name='agentx.acceptance',
        string='Acceptance',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(string='Sequence', default=10)
    description = fields.Char(
        string='Criteria',
        required=True,
    )
    result = fields.Selection(
        selection=[
            ('pass', 'Pass'),
            ('fail', 'Fail'),
            ('na', 'N/A'),
        ],
        string='Result',
    )
    notes = fields.Text(string='Notes')


class AgentxAcceptance(models.Model):
    _name = 'agentx.acceptance'
    _description = 'AgentX Acceptance Criteria'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'project_id, id'
    _rec_name = 'name'

    # ── Core fields ───────────────────────────────────────────────────────────
    name = fields.Char(
        string='Acceptance Title',
        required=True,
        tracking=True,
    )
    code = fields.Char(
        string='Reference',
        readonly=True,
        copy=False,
        index=True,
    )
    project_id = fields.Many2one(
        comodel_name='agentx.project',
        string='Project',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True,
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('in_review', 'In Review'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
    )

    # ── Details ───────────────────────────────────────────────────────────────
    description = fields.Html(string='Description')
    criteria_line_ids = fields.One2many(
        comodel_name='agentx.acceptance.line',
        inverse_name='acceptance_id',
        string='Criteria',
    )

    # ── Review ────────────────────────────────────────────────────────────────
    reviewer_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Reviewer',
        tracking=True,
    )
    date_submitted = fields.Date(
        string='Date Submitted',
        readonly=True,
    )
    date_reviewed = fields.Date(
        string='Date Reviewed',
        tracking=True,
        readonly=True,
    )
    review_notes = fields.Text(string='Review Notes')

    # ── Computed ──────────────────────────────────────────────────────────────
    criteria_count = fields.Integer(
        compute='_compute_criteria_stats',
        string='Total Criteria',
    )
    passed_count = fields.Integer(
        compute='_compute_criteria_stats',
        string='Passed',
    )
    failed_count = fields.Integer(
        compute='_compute_criteria_stats',
        string='Failed',
    )

    # ── ORM overrides ─────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = (
                    self.env['ir.sequence'].next_by_code('agentx.acceptance') or '/'
                )
        return super().create(vals_list)

    # ── Compute methods ───────────────────────────────────────────────────────
    @api.depends('criteria_line_ids', 'criteria_line_ids.result')
    def _compute_criteria_stats(self):
        for acceptance in self:
            lines = acceptance.criteria_line_ids
            acceptance.criteria_count = len(lines)
            acceptance.passed_count = len(lines.filtered(lambda l: l.result == 'pass'))
            acceptance.failed_count = len(lines.filtered(lambda l: l.result == 'fail'))

    # ── State machine actions ─────────────────────────────────────────────────
    def action_submit(self):
        """Transition Draft → In Review."""
        for acceptance in self:
            if acceptance.state != 'draft':
                raise UserError(_("Only draft acceptance records can be submitted for review."))
            if not acceptance.criteria_line_ids:
                raise UserError(_("Please add at least one acceptance criterion before submitting."))
            acceptance.write({
                'state': 'in_review',
                'date_submitted': fields.Date.today(),
            })
            acceptance.message_post(body=_("Acceptance criteria submitted for review."))

    def action_approve(self):
        """Transition In Review → Approved."""
        for acceptance in self:
            if acceptance.state != 'in_review':
                raise UserError(_("Only in-review acceptance records can be approved."))
            failed = acceptance.criteria_line_ids.filtered(lambda l: l.result == 'fail')
            if failed:
                raise UserError(
                    _("Cannot approve: %d criteria are marked as failed.")
                    % len(failed)
                )
            acceptance.write({
                'state': 'approved',
                'date_reviewed': fields.Date.today(),
            })
            acceptance.message_post(body=_("Acceptance criteria approved. Project handover confirmed."))

    def action_reject(self):
        """Transition In Review → Rejected."""
        for acceptance in self:
            if acceptance.state != 'in_review':
                raise UserError(_("Only in-review acceptance records can be rejected."))
            acceptance.write({
                'state': 'rejected',
                'date_reviewed': fields.Date.today(),
            })
            acceptance.message_post(
                body=_("Acceptance criteria rejected. Notes: %s") % (acceptance.review_notes or '')
            )

    def action_resubmit(self):
        """Transition Rejected → In Review."""
        for acceptance in self:
            if acceptance.state != 'rejected':
                raise UserError(_("Only rejected acceptance records can be resubmitted."))
            acceptance.write({
                'state': 'in_review',
                'date_reviewed': False,
            })
            acceptance.message_post(body=_("Acceptance criteria resubmitted for review."))

    def action_reset_draft(self):
        """Transition any state → Draft."""
        for acceptance in self:
            if acceptance.state == 'approved':
                raise UserError(_("Approved acceptance criteria cannot be reset."))
            acceptance.write({
                'state': 'draft',
                'date_submitted': False,
                'date_reviewed': False,
            })
            acceptance.message_post(body=_("Acceptance criteria reset to draft."))
