# -*- coding: utf-8 -*-
"""
Extends account.analytic.line (timesheet) to link entries to AgentX tasks.

Blueprint note:
  `agentx_task_id` is added to `account.analytic.line` so that hours logged
  via HR Timesheet appear on the AgentX Task form under the Timesheets tab.
"""
import logging
from odoo import fields, models

_logger = logging.getLogger(__name__)


class AccountAnalyticLineExt(models.Model):
    _inherit = 'account.analytic.line'

    agentx_task_id = fields.Many2one(
        comodel_name='agentx.task',
        string='AgentX Task',
        index=True,
        ondelete='set null',
        help='Link this timesheet entry to an AgentX task.',
    )
