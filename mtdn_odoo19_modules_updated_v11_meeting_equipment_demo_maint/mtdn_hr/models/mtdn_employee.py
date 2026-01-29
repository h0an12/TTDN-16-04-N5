# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class MtdnEmployee(models.Model):
    _name = "mtdn.employee"
    _description = "MTDN Employee"
    _order = "code, name"

    code = fields.Char(
        string="Mã nhân viên",
        required=True,
        copy=False,
        default="New",
        index=True,
    )
    name = fields.Char(string="Họ và tên", required=True, index=True)

    gender = fields.Selection(
        selection=[
            ("male", "Nam"),
            ("female", "Nữ"),
            ("other", "Khác"),
        ],
        string="Giới tính",
        default="other",
    )
    birthday = fields.Date(string="Ngày sinh")

    email = fields.Char(string="Email")
    phone = fields.Char(string="Số điện thoại")

    department_id = fields.Many2one(
        "mtdn.department",
        string="Phòng ban",
        ondelete="set null",
        index=True,
    )
    job_id = fields.Many2one(
        "mtdn.job",
        string="Chức danh",
        ondelete="set null",
        index=True,
    )

    manager_id = fields.Many2one(
        "mtdn.employee",
        string="Quản lý trực tiếp",
        ondelete="set null",
    )

    start_date = fields.Date(string="Ngày vào làm", required=True, default=fields.Date.context_today)
    leave_date = fields.Date(string="Ngày nghỉ việc")

    state = fields.Selection(
        selection=[
            ("probation", "Thử việc"),
            ("working", "Đang làm"),
            ("on_leave", "Tạm nghỉ"),
            ("resigned", "Nghỉ việc"),
        ],
        string="Trạng thái",
        required=True,
        default="probation",
        index=True,
    )
    active = fields.Boolean(default=True)
    note = fields.Text(string="Ghi chú")

    _sql_constraints = [
        ("mtdn_employee_code_uniq", "unique(code)", "Mã nhân viên phải là duy nhất."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("code") or vals.get("code") == "New":
                vals["code"] = self.env["ir.sequence"].next_by_code("mtdn.employee") or "New"
        return super().create(vals_list)

    @api.constrains("start_date", "leave_date")
    def _check_leave_date(self):
        for rec in self:
            if rec.leave_date and rec.start_date and rec.leave_date < rec.start_date:
                raise ValidationError("Ngày nghỉ việc không được nhỏ hơn ngày vào làm.")

    @api.constrains("state", "leave_date")
    def _check_leave_date_when_resigned(self):
        for rec in self:
            if rec.state == "resigned" and not rec.leave_date:
                raise ValidationError("Khi trạng thái là 'Nghỉ việc' bạn phải nhập Ngày nghỉ việc.")

    @api.onchange("state")
    def _onchange_state(self):
        for rec in self:
            if rec.state == "resigned" and not rec.leave_date:
                rec.leave_date = fields.Date.context_today(rec)

    @api.onchange("department_id")
    def _onchange_department_id_domain_job(self):
        """Khi chọn phòng ban, chỉ cho phép chọn chức danh thuộc phòng ban đó.

        Đồng thời nếu đổi phòng ban khiến chức danh đang chọn không còn hợp lệ
        thì tự động xoá chức danh để tránh dữ liệu sai.
        """
        for rec in self:
            if rec.job_id and rec.department_id and rec.job_id.department_id != rec.department_id:
                rec.job_id = False

            if rec.department_id:
                return {"domain": {"job_id": [("department_id", "=", rec.department_id.id)]}}
            return {"domain": {"job_id": []}}

    def action_set_probation(self):
        self.write({"state": "probation", "active": True})

    def action_set_working(self):
        self.write({"state": "working", "active": True})

    def action_set_on_leave(self):
        self.write({"state": "on_leave", "active": True})

    def action_resign(self):
        today = fields.Date.context_today(self)
        for rec in self:
            vals = {"state": "resigned", "active": False}
            if not rec.leave_date:
                vals["leave_date"] = today
            rec.write(vals)

    @api.model
    def mtdn_get_dashboard_data(self):
        """Return small aggregated data for the HR dashboard (used by JS client action)."""
        Employee = self.with_context(active_test=False)
        Department = self.env["mtdn.department"].sudo()
        Job = self.env["mtdn.job"].sudo()

        return {
            "employee_total": Employee.search_count([]),
            "probation": Employee.search_count([("state", "=", "probation")]),
            "working": Employee.search_count([("state", "=", "working")]),
            "on_leave": Employee.search_count([("state", "=", "on_leave")]),
            "resigned": Employee.search_count([("state", "=", "resigned")]),
            "department_total": Department.search_count([]),
            "job_total": Job.search_count([]),
        }

