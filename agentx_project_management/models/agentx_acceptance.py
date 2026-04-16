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
            ('submitted', 'Submitted'),
            ('accepted', 'Accepted'),
            ('rejected', 'Rejected'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
    )

    # ── Handover details ──────────────────────────────────────────────────────
    date = fields.Date(
        string='Acceptance Date',
        tracking=True,
        help='The formal date on which the customer accepted the deliverables.',
    )
    customer_id = fields.Many2one(
        comodel_name='res.partner',
        string='Customer',
        tracking=True,
        index=True,
    )
    signee_name = fields.Char(
        string='Signee Name',
        help='Full name of the person signing off on behalf of the customer.',
    )
    sprint_ids = fields.Many2many(
        comodel_name='agentx.sprint',
        relation='agentx_acceptance_sprint_rel',
        column1='acceptance_id',
        column2='sprint_id',
        string='Covered Sprints',
        help='Sprints whose deliverables are covered by this acceptance record.',
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

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _get_customer_partner_ids(self):
        """Return a list of partner ids to notify (customer contact if set)."""
        self.ensure_one()
        partner_ids = []
        if self.customer_id:
            partner_ids.append(self.customer_id.id)
        return partner_ids

    def _subscribe_customer(self):
        """Add the customer as a follower so they receive chatter notifications."""
        self.ensure_one()
        if self.customer_id:
            self.message_subscribe(partner_ids=[self.customer_id.id])

    # ── State machine actions ─────────────────────────────────────────────────
    def action_submit(self):
        """Transition Draft → Submitted (sends to customer for review)."""
        for acceptance in self:
            if acceptance.state != 'draft':
                raise UserError(
                    _("Only draft acceptance records can be submitted.")
                )
            if not acceptance.criteria_line_ids:
                raise UserError(
                    _("Please add at least one acceptance criterion before submitting.")
                )
            acceptance._subscribe_customer()
            acceptance.write({
                'state': 'submitted',
                'date_submitted': fields.Date.today(),
            })
            acceptance.message_post(
                body=_(
                    "Acceptance record <b>%s</b> has been submitted to the customer for review. "
                    "The project team has been notified."
                ) % acceptance.name,
                partner_ids=acceptance._get_customer_partner_ids(),
            )
            _logger.info(
                "Acceptance %s (id=%s) submitted for customer review.", acceptance.name, acceptance.id
            )

    def action_accept(self):
        """Transition Submitted → Accepted."""
        for acceptance in self:
            if acceptance.state != 'submitted':
                raise UserError(
                    _("Only submitted acceptance records can be accepted.")
                )
            failed = acceptance.criteria_line_ids.filtered(lambda l: l.result == 'fail')
            if failed:
                raise UserError(
                    _("Cannot accept: %d criteria are still marked as failed. "
                      "Please resolve them first.")
                    % len(failed)
                )
            acceptance.write({
                'state': 'accepted',
                'date_reviewed': fields.Date.today(),
            })
            # Notify project team and customer
            acceptance.message_post(
                body=_(
                    "✅ Acceptance record <b>%s</b> has been <b>accepted</b>. "
                    "Project handover confirmed. Signed off by: %s"
                ) % (acceptance.name, acceptance.signee_name or _("N/A")),
                partner_ids=acceptance._get_customer_partner_ids(),
            )
            _logger.info(
                "Acceptance %s (id=%s) accepted.", acceptance.name, acceptance.id
            )
            # Inform if all project acceptances are now accepted
            project = acceptance.project_id
            if project:
                all_acceptances = project.acceptance_ids
                pending = all_acceptances.filtered(lambda a: a.state != 'accepted')
                if not pending and all_acceptances:
                    project.message_post(
                        body=_(
                            "🎉 All acceptance criteria for this project have been accepted. "
                            "The project is now eligible to be closed."
                        )
                    )

    def action_reject(self):
        """Transition Submitted → Rejected (customer raised objections)."""
        for acceptance in self:
            if acceptance.state != 'submitted':
                raise UserError(
                    _("Only submitted acceptance records can be rejected.")
                )
            acceptance.write({
                'state': 'rejected',
                'date_reviewed': fields.Date.today(),
            })
            acceptance.message_post(
                body=_(
                    "❌ Acceptance record <b>%s</b> has been <b>rejected</b> by the customer. "
                    "Review notes: %s"
                ) % (acceptance.name, acceptance.review_notes or _("(none)")),
                partner_ids=acceptance._get_customer_partner_ids(),
            )
            _logger.info(
                "Acceptance %s (id=%s) rejected.", acceptance.name, acceptance.id
            )

    def action_resubmit(self):
        """Transition Rejected → Submitted (address objections and resubmit)."""
        for acceptance in self:
            if acceptance.state != 'rejected':
                raise UserError(
                    _("Only rejected acceptance records can be resubmitted.")
                )
            acceptance.write({
                'state': 'submitted',
                'date_reviewed': False,
            })
            acceptance.message_post(
                body=_(
                    "Acceptance record <b>%s</b> has been resubmitted to the customer after "
                    "addressing their objections."
                ) % acceptance.name,
                partner_ids=acceptance._get_customer_partner_ids(),
            )

    def action_reset_draft(self):
        """Transition Submitted/Rejected → Draft."""
        for acceptance in self:
            if acceptance.state == 'accepted':
                raise UserError(_("Accepted acceptance records cannot be reset to draft."))
            acceptance.write({
                'state': 'draft',
                'date_submitted': False,
                'date_reviewed': False,
            })
            acceptance.message_post(body=_("Acceptance record reset to draft."))
