# -*- coding: utf-8 -*-
{
    'name': 'AgentX Project Management',
    'version': '18.0.1.0.0',
    'summary': 'Manage full software project lifecycle: requirements, sprints, tasks, bugs, and acceptance.',
    'description': """
        AgentX Project Management Module
        =================================
        Manages the entire software project lifecycle for IT/outsourcing companies:
        - Project and team management
        - Sprint planning and tracking
        - Task and user story management
        - Bug tracking with severity levels
        - Milestone tracking
        - Acceptance criteria and handover
        - Timesheet integration (HR Timesheet)
        - Internal communication via Discuss
    """,
    'author': 'OdooAgentX',
    'website': 'https://github.com/khaid2849/odoo-agentx',
    'category': 'Project',
    'depends': [
        'base',
        'mail',
        'hr',
        'hr_timesheet',
    ],
    'data': [
        # 1. Security first
        'security/security.xml',
        'security/ir.model.access.csv',
        # 2. Data (sequences, cron)
        'data/sequence_data.xml',
        'data/ir_cron.xml',
        # 3. Reports
        'reports/report_action.xml',
        'reports/report_acceptance_template.xml',
        # 4. Views last
        'views/agentx_project_views.xml',
        'views/agentx_sprint_views.xml',
        'views/agentx_task_views.xml',
        'views/agentx_bug_views.xml',
        'views/agentx_milestone_views.xml',
        'views/agentx_acceptance_views.xml',
        'views/agentx_timesheet_views.xml',
        'views/menu_views.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'images': ['static/description/icon.png',],
}
