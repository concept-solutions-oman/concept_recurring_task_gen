# -*- coding: utf-8 -*-
{
    'name': "Project Recurring Tasks",
    'summary': """
        Allows creating recurring tasks with a schedule and previews upcoming dates.
    """,
    'description': """
        This module extends the standard project tasks to allow them to be recurrent.
        You can define a recurrence pattern (e.g., every week on Monday and Thursday)
        and the system will show a preview of the next 5 upcoming dates.
    """,
    'author': "Concept Solutions LLC",
    'website': "https://www.csloman.com/",
    'category': 'Project',
    'version': '17.0.1.0.3',
    'depends': ['project'], 
    'data': [
        'views/project_task_views.xml',
        'views/parent_task_views.xml',
        'views/magic_hider.xml',
        'data/ir_cron_data.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'OPL-1',
    'price': 360.00,
    'currency': 'USD',
    'images': ['static/description/banner.png'],
}