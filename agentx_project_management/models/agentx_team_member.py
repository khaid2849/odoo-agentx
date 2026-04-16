# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class AgentxTeamMember(models.Model):
    _name = 'agentx.team.member'
    _description = 'AgentX Team Member'
    _order = 'project_id, role, employee_id'
    _rec_name = 'employee_id'

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
    date_start = fields.Date(string='Start Date')
    date_end = fields.Date(string='End Date')
    allocation_percent = fields.Float(
        string='Allocation (%)',
        default=100.0,
        digits=(5, 2),
        help='Percentage of working time allocated to this project.',
    )
    notes = fields.Text(string='Notes')

    # ── SQL constraints ───────────────────────────────────────────────────────
    _sql_constraints = [
        (
            'employee_project_uniq',
            'UNIQUE(project_id, employee_id)',
            'An employee can only be assigned to a project once!',
        ),
    ]

    # ── Constraints ───────────────────────────────────────────────────────────
    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for member in self:
            if member.date_end and member.date_start and member.date_end < member.date_start:
                raise ValidationError(
                    _("Team member end date cannot be before start date.")
                )

    @api.constrains('allocation_percent')
    def _check_allocation(self):
        for member in self:
            if not (0.0 < member.allocation_percent <= 100.0):
                raise ValidationError(
                    _("Allocation percentage must be between 0 and 100.")
                )
