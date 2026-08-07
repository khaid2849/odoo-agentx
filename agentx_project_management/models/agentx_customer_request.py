# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class AgentxCustomerRequest(models.Model):
    _name = 'agentx.customer.request'
    _description = 'AgentX Customer Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, date_received desc, id desc'
    _rec_name = 'name'

    # ── Core fields ───────────────────────────────────────────────────────────
    name = fields.Char(
        string='Request Title',
        required=True,
        tracking=True,
    )
    code = fields.Char(
        string='Reference',
        readonly=True,
        copy=False,
        index=True,
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('in_analysis', 'In Analysis'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
        ],
        string='Status',
        default='draft',
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
    description = fields.Html(string='Description')
    date_received = fields.Date(
        string='Date Received',
        default=fields.Date.today,
        required=True,
        tracking=True,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    project_id = fields.Many2one(
        comodel_name='agentx.project',
        string='Project',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True,
    )
    customer_id = fields.Many2one(
        comodel_name='res.partner',
        string='Customer',
        tracking=True,
        index=True,
    )
    assigned_to_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Assigned To',
        tracking=True,
        index=True,
    )
    task_ids = fields.One2many(
        comodel_name='agentx.task',
        inverse_name='request_id',
        string='Tasks',
    )

    # ── Computed ──────────────────────────────────────────────────────────────
    task_count = fields.Integer(
        compute='_compute_task_count',
        string='Tasks',
    )

    # ── SQL Constraints ───────────────────────────────────────────────────────
    _sql_constraints = [
        ('code_uniq', 'UNIQUE(code)', 'Request reference must be unique!'),
    ]

    # ── ORM overrides ─────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = (
                    self.env['ir.sequence'].next_by_code('agentx.customer.request') or '/'
                )
        return super().create(vals_list)

    # ── Compute methods ───────────────────────────────────────────────────────
    @api.depends('task_ids')
    def _compute_task_count(self):
        for request in self:
            request.task_count = len(request.task_ids)

    # ── Onchange ──────────────────────────────────────────────────────────────
    @api.onchange('project_id')
    def _onchange_project_id(self):
        """Auto-fill customer from project when project changes."""
        if self.project_id and self.project_id.customer_id:
            self.customer_id = self.project_id.customer_id

    # ── State machine actions ─────────────────────────────────────────────────
    def action_confirm(self):
        """Transition Draft → Confirmed."""
        for req in self:
            if req.state != 'draft':
                raise UserError(_("Only draft requests can be confirmed."))
            req.state = 'confirmed'
            req.message_post(body=_("Request confirmed."))

    def action_analyze(self):
        """Transition Confirmed → In Analysis."""
        for req in self:
            if req.state != 'confirmed':
                raise UserError(_("Only confirmed requests can be moved to analysis."))
            req.state = 'in_analysis'
            req.message_post(body=_("Request moved to analysis."))

    def action_approve(self):
        """Transition In Analysis → Approved."""
        for req in self:
            if req.state != 'in_analysis':
                raise UserError(_("Only requests under analysis can be approved."))
            req.state = 'approved'
            req.message_post(body=_("Request approved."))

    def action_reject(self):
        """Transition In Analysis → Rejected."""
        for req in self:
            if req.state != 'in_analysis':
                raise UserError(_("Only requests under analysis can be rejected."))
            req.state = 'rejected'
            req.message_post(body=_("Request rejected."))

    def action_reset_to_draft(self):
        """Transition Rejected → Draft."""
        for req in self:
            if req.state != 'rejected':
                raise UserError(_("Only rejected requests can be reset to draft."))
            req.state = 'draft'
            req.message_post(body=_("Request reset to draft."))

    # ── Smart button actions ──────────────────────────────────────────────────
    def action_view_tasks(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tasks'),
            'res_model': 'agentx.task',
            'view_mode': 'list,kanban,form',
            'domain': [('request_id', '=', self.id)],
            'context': {
                'default_request_id': self.id,
                'default_project_id': self.project_id.id,
            },
        }
