# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class AgentxResourceAllocation(models.Model):
    _name = 'agentx.resource.allocation'
    _description = 'AgentX Resource Allocation'
    _order = 'project_id, start_date, employee_id'
    _rec_name = 'employee_id'

    # ── Core fields ───────────────────────────────────────────────────────────
    project_id = fields.Many2one(
        comodel_name='agentx.project',
        string='Project',
        required=True,
        ondelete='cascade',
        index=True,
    )
    employee_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Employee',
        required=True,
        index=True,
    )
    role = fields.Selection(
        selection=[
            ('pm', 'Project Manager'),
            ('ba', 'Business Analyst'),
            ('dev', 'Developer'),
            ('qa', 'QA Engineer'),
            ('designer', 'Designer'),
            ('devops', 'DevOps'),
            ('other', 'Other'),
        ],
        string='Role',
        required=True,
        default='dev',
    )
    allocation_pct = fields.Float(
        string='Allocation (%)',
        required=True,
        default=100.0,
        digits=(5, 2),
        help='Percentage of working time allocated to this project for this period.',
    )
    start_date = fields.Date(
        string='Start Date',
        required=True,
        index=True,
    )
    end_date = fields.Date(
        string='End Date',
        index=True,
    )
    notes = fields.Text(string='Notes')

    # ── Constraints ───────────────────────────────────────────────────────────
    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for alloc in self:
            if alloc.end_date and alloc.start_date and alloc.end_date < alloc.start_date:
                raise ValidationError(
                    _("Allocation end date cannot be before start date.")
                )

    @api.constrains('allocation_pct')
    def _check_allocation_pct(self):
        for alloc in self:
            if not (0.0 < alloc.allocation_pct <= 100.0):
                raise ValidationError(
                    _("Allocation percentage must be between 0 and 100.")
                )
