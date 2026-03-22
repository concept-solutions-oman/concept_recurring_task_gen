# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

from datetime import timedelta
from dateutil.relativedelta import relativedelta

class ProjectTask(models.Model):
    _inherit = 'project.task'

    # (Fields are the same as before, no changes here)
    is_recurrent = fields.Boolean(string="Recurrent", default=False)
    recurrence_start_date = fields.Date(string="Start Date", default=fields.Date.context_today)
    recurrence_interval = fields.Integer(string="Repeat Every", default=1)
    recurrence_unit = fields.Selection(
        [('days', 'Days'), ('weeks', 'Weeks'), ('months', 'Months'), ('years', 'Years')],
        string="Unit", default='weeks', required=True
    )
    recurs_on_sun = fields.Boolean(string="Sun")
    recurs_on_mon = fields.Boolean(string="Mon")
    recurs_on_tue = fields.Boolean(string="Tue")
    recurs_on_wed = fields.Boolean(string="Wed")
    recurs_on_thu = fields.Boolean(string="Thu")
    recurs_on_fri = fields.Boolean(string="Fri")
    recurs_on_sat = fields.Boolean(string="Sat")
    recurrence_end_type = fields.Selection(
        [('forever', 'Forever'), ('until', 'Until')],
        string="Until", default='forever'
    )
    recurrence_end_date = fields.Date(string="End Date")
    last_recurrence_date = fields.Date(string="Last Recurrence", readonly=True, copy=False)
    recurrence_preview = fields.Html(
        string="Upcoming Dates",
        compute='_compute_recurrence_preview',
        store=False
    )
    # (parent task)
    parent_id = fields.Many2one(
        'project.task',
        string="Parent Task",
        readonly=True,  
    )

    @api.onchange('recurring_task')
    def _onchange_recurring_task(self):
        """Automatically enable is_recurrent when recurring_task is checked."""
        if self.recurring_task:
            self.is_recurrent = True
        else:
            self.is_recurrent = False

    @api.model
    def create(self, vals):
        """Ensure is_recurrent is True if recurring_task is enabled on creation."""
        if vals.get('recurring_task'):
            vals['is_recurrent'] = True
        return super().create(vals)

    def write(self, vals):
        """Ensure is_recurrent syncs with recurring_task on update."""
        if 'recurring_task' in vals:
            vals['is_recurrent'] = bool(vals['recurring_task'])
        return super().write(vals)

    def _get_next_recurrence_date(self, base_date):
        """ Robustly calculates the very next occurrence date from a given base date """
        self.ensure_one()
        if self.recurrence_unit == 'weeks':
            selected_weekdays = {
                idx for idx, day_bool in enumerate([
                    self.recurs_on_mon, self.recurs_on_tue, self.recurs_on_wed,
                    self.recurs_on_thu, self.recurs_on_fri, self.recurs_on_sat,
                    self.recurs_on_sun
                ]) if day_bool
            }
            if not selected_weekdays: return None
            
            # Start checking from the day after the base_date
            next_date = base_date + timedelta(days=1)
            # Iterate a max of 400 days to find the next valid date to prevent infinite loops
            for _ in range(400):
                # Check if the day of the week is correct
                if next_date.weekday() in selected_weekdays:
                    # Check if the week interval is correct
                    weeks_passed = (next_date - self.recurrence_start_date).days // 7
                    if weeks_passed % self.recurrence_interval == 0:
                        return next_date
                next_date += timedelta(days=1)

        else: # For days, months, years
            delta = relativedelta(**{self.recurrence_unit: self.recurrence_interval})
            return base_date + delta
        return None

    @api.model
    def _cron_generate_recurring_tasks(self):
        today = fields.Date.today()
        domain = [
            ('is_recurrent', '=', True), ('recurrence_start_date', '<=', today),
            '|', ('recurrence_end_type', '=', 'forever'), ('recurrence_end_date', '>=', today)
        ]
        recurrent_tasks = self.search(domain)

        for task in recurrent_tasks:
            # If nothing has been generated, start from the day before the official start date
            last_date = task.last_recurrence_date or (task.recurrence_start_date - timedelta(days=1))
            
            while True:
                next_due_date = task._get_next_recurrence_date(last_date)
                
                if not next_due_date or next_due_date > today or (task.recurrence_end_date and next_due_date > task.recurrence_end_date):
                    break

                # --- CHANGE 1: TASK TITLE WITH DATE ---
                # The name of the new task will include the date.
                new_task_name = f"{task.name}: {next_due_date.strftime('%d/%m/%Y')}"

                new_task_vals = {
                    'name': new_task_name,
                    'project_id': task.project_id.id,
                    'user_ids': [(6, 0, task.user_ids.ids)],
                    'description': task.description,
                    'date_deadline': next_due_date,
                    'recurring_task': False,
                    'parent_id': task.id,
                    'tag_ids': [(6, 0, task.tag_ids.ids)],
                }
                self.create(new_task_vals)
                task.write({'last_recurrence_date': next_due_date})
                last_date = next_due_date

    @api.constrains('recurrence_interval')
    def _check_recurrence_interval(self):
        for task in self:
            if task.is_recurrent and task.recurrence_interval < 1:
                raise ValidationError(_("The recurrence interval must be 1 or greater."))

    @api.depends(
        'is_recurrent', 'recurrence_interval', 'recurrence_unit', 'recurrence_start_date',
        'recurs_on_sun', 'recurs_on_mon', 'recurs_on_tue', 'recurs_on_wed',
        'recurs_on_thu', 'recurs_on_fri', 'recurs_on_sat',
        'recurrence_end_type', 'recurrence_end_date'
    )
    def _compute_recurrence_preview(self):
        """
        Generates a preview of upcoming dates and calculates the total count if an end date is set.
        """
        for task in self:
            if not task.is_recurrent or not task.recurrence_start_date:
                task.recurrence_preview = False
                continue

            all_dates = []
            start_date = task.recurrence_start_date
            end_date = task.recurrence_end_date if task.recurrence_end_type == 'until' else None
            
            # Set a practical limit for 'forever' previews
            preview_limit_date = start_date + relativedelta(years=5)
            effective_end_date = end_date or preview_limit_date

            # --- CHANGE 2: TOTAL TASK COUNT LOGIC ---
            # This logic now calculates all dates up to the end date (or a 5-year limit for 'forever')
            
            last_date = start_date - timedelta(days=1)
            while True:
                next_date = task._get_next_recurrence_date(last_date)
                if not next_date or next_date > effective_end_date:
                    break
                # Ensure we don't add dates before the actual start_date
                if next_date >= start_date:
                    all_dates.append(next_date)
                last_date = next_date

            if not all_dates:
                task.recurrence_preview = "<p>No upcoming dates found with the current settings.</p>"
                continue

            # Prepare the preview list (only show the first 5)
            preview_list = all_dates[:5]
            date_items = "".join([f"<li>{d.strftime('%d/%m/%Y')}</li>" for d in preview_list])
            ellipsis = "<li>...</li>" if len(all_dates) > 5 else ""
            
            # Prepare the total count message
            total_count_msg = ""
            if end_date:
                total_count_msg = f"<br/><b>Total tasks to be created: {len(all_dates)}</b>"

            # Build the final HTML message
            task.recurrence_preview = f"""
                <p>A new task will be created on the following dates:</p>
                <ul>{date_items}{ellipsis}</ul>
                {total_count_msg}
            """