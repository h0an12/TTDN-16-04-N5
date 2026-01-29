# -*- coding: utf-8 -*-
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class MtdnAsset(models.Model):
    _name = "mtdn.asset"
    _description = "MTDN Asset"
    _order = "code, name"

    code = fields.Char(string="Mã tài sản", required=True, copy=False, default="New", index=True)
    name = fields.Char(string="Tên tài sản", required=True, index=True)

    category_id = fields.Many2one(
        "mtdn.asset.category",
        string="Loại tài sản",
        ondelete="restrict",
        required=True,
        index=True,
    )

    # Meeting equipment classification (used by Meeting Room module)
    equipment_type_id = fields.Many2one(
        "mtdn.asset.equipment.type",
        string="Loại thiết bị",
        ondelete="restrict",
        index=True,
        help="Dùng cho nhóm 'Thiết bị phòng họp' để lọc phòng theo nhu cầu thiết bị.",
    )

    company_id = fields.Many2one(
        "res.company",
        string="Công ty",
        default=lambda self: self.env.company,
        required=True,
        index=True,
    )

    purchase_date = fields.Date(string="Ngày mua")
    in_service_date = fields.Date(string="Ngày đưa vào sử dụng")

    partner_id = fields.Many2one(
        "res.partner",
        string="Đối tác",
        help="Nhà cung cấp / đối tác liên quan tới tài sản (tùy chọn).",
        ondelete="set null",
    )

    branch_id = fields.Many2one(
        "mtdn.branch",
        string="Chi nhánh",
        ondelete="set null",
        index=True,
    )

    quantity = fields.Integer(string="Số lượng", default=1)

    currency_id = fields.Many2one(
        "res.currency",
        string="Tiền tệ",
        default=lambda self: self.env.company.currency_id,
        required=True,
    )
    value = fields.Monetary(string="Giá trị", currency_field="currency_id")

    # ------------------------------------------------------------
    # Depreciation (multiple methods + flexible unit)
    # ------------------------------------------------------------
    depreciation_method = fields.Selection(
        selection=[
            ("none", "Không khấu hao"),
            ("linear", "Đường thẳng"),
            ("declining", "Số dư giảm dần"),
            ("syd", "Tổng số năm (SYD)"),
        ],
        string="Phương pháp khấu hao",
        required=True,
        default="linear",
        index=True,
        help="Có thể chỉnh khi tạo/sửa tài sản. Mặc định lấy từ loại tài sản.",
    )

    depreciation_unit = fields.Selection(
        selection=[("month", "Tháng"), ("year", "Năm")],
        string="Đơn vị khấu hao",
        required=True,
        default="year",
        help="Đơn vị của số kỳ khấu hao.",
    )

    # Keep the original field name to avoid breaking existing views/data.
    depreciation_years = fields.Integer(
        string="Số kỳ khấu hao",
        default=3,
        help="Số kỳ khấu hao theo đơn vị đã chọn. Ví dụ: 36 (tháng) hoặc 3 (năm).",
    )

    declining_factor = fields.Float(
        string="Hệ số giảm dần",
        default=2.0,
        help="Dùng cho phương pháp số dư giảm dần (mặc định 2.0 = double-declining).",
    )
    depreciation_start_date = fields.Date(string="Ngày bắt đầu khấu hao")

    depreciation_per_year = fields.Monetary(
        string="Khấu hao / kỳ",
        currency_field="currency_id",
        compute="_compute_depreciation_values",
        store=True,
        readonly=True,
    )
    accumulated_depreciation = fields.Monetary(
        string="Khấu hao lũy kế",
        currency_field="currency_id",
        compute="_compute_depreciation_values",
        store=True,
        readonly=True,
    )
    book_value = fields.Monetary(
        string="Giá trị còn lại",
        currency_field="currency_id",
        compute="_compute_depreciation_values",
        store=True,
        readonly=True,
    )

    # ------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------
    next_maintenance_date = fields.Date(string="Ngày bảo trì tiếp theo")
    maintenance_overdue = fields.Boolean(
        string="Quá hạn bảo trì",
        compute="_compute_maintenance_overdue",
        store=True,
        readonly=True,
    )

    state = fields.Selection(
        selection=[
            ("available", "Sẵn sàng"),
            ("in_use", "Đang sử dụng"),
            ("maintenance", "Bảo trì"),
            ("broken", "Hỏng"),
        ],
        string="Trạng thái",
        required=True,
        default="available",
        index=True,
    )

    # Assignment (link directly to custom HR models)
    employee_id = fields.Many2one(
        "mtdn.employee",
        string="Gán cho nhân viên",
        ondelete="set null",
        index=True,
    )
    department_id = fields.Many2one(
        "mtdn.department",
        string="Gán cho phòng ban",
        ondelete="set null",
        index=True,
    )

    # Attachments per asset
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "mtdn_asset_ir_attachment_rel",
        "asset_id",
        "attachment_id",
        string="Tài liệu",
        help="Tài liệu đính kèm riêng cho từng tài sản (hướng dẫn, hóa đơn, bảo hành, ...).",
    )

    active = fields.Boolean(default=True)
    note = fields.Text(string="Ghi chú")

    _sql_constraints = [
        ("mtdn_asset_code_uniq", "unique(code)", "Mã tài sản phải là duy nhất."),
    ]

    # ------------------------------------------------------------
    # ORM
    # ------------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        """Support setting default category from client-side action context.

        In Odoo 17+ the action context is evaluated on the client, so we cannot
        use ref('xmlid') inside XML contexts. Instead, actions pass a stable
        category code (or xmlid string), which we resolve here.
        """
        res = super().default_get(fields_list)

        ctx = self.env.context or {}
        # If the action passes category code, resolve it to an ID
        if not res.get("category_id") and ctx.get("default_category_code"):
            code = ctx.get("default_category_code")
            cat = self.env["mtdn.asset.category"].search([("code", "=", code)], limit=1)
            if cat:
                res["category_id"] = cat.id

        # Backward compatible: if someone passed an xmlid string as default_category_id
        if not res.get("category_id") and isinstance(ctx.get("default_category_id"), str):
            xmlid = ctx.get("default_category_id")
            try:
                res["category_id"] = self.env.ref(xmlid).id
            except Exception:
                pass

        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("code") or vals.get("code") == "New":
                vals["code"] = self.env["ir.sequence"].next_by_code("mtdn.asset") or "New"

            # allow creating from Meeting Equipment menu without hardcoding IDs
            if not vals.get("category_id") and self.env.context.get("default_category_code"):
                code = self.env.context.get("default_category_code")
                cat = self.env["mtdn.asset.category"].search([("code", "=", code)], limit=1)
                if cat:
                    vals["category_id"] = cat.id

            # default depreciation settings from category (but keep editable on asset)
            if vals.get("category_id"):
                cat = self.env["mtdn.asset.category"].browse(vals["category_id"])
                if cat.exists():
                    vals.setdefault("depreciation_method", cat.depreciation_method)
                    vals.setdefault("depreciation_unit", cat.depreciation_unit)
                    vals.setdefault("depreciation_years", cat.depreciation_years)
                    vals.setdefault("declining_factor", cat.declining_factor)

            # sensible default for depreciation start date
            if not vals.get("depreciation_start_date"):
                vals["depreciation_start_date"] = vals.get("in_service_date") or vals.get("purchase_date")
        return super().create(vals_list)

    def write(self, vals):
        # if category changed and user didn't explicitly set depreciation fields,
        # take defaults from the new category (still editable afterwards)
        if vals.get("category_id"):
            cat = self.env["mtdn.asset.category"].browse(vals["category_id"])
            if cat.exists():
                vals.setdefault("depreciation_method", cat.depreciation_method)
                vals.setdefault("depreciation_unit", cat.depreciation_unit)
                vals.setdefault("depreciation_years", cat.depreciation_years)
                vals.setdefault("declining_factor", cat.declining_factor)

        # keep depreciation start date populated if user sets service date later
        if "depreciation_start_date" not in vals and ("in_service_date" in vals or "purchase_date" in vals):
            for rec in self:
                if not rec.depreciation_start_date:
                    vals.setdefault(
                        "depreciation_start_date",
                        vals.get("in_service_date") or vals.get("purchase_date") or rec.in_service_date or rec.purchase_date,
                    )
                    break
        return super().write(vals)

    # ------------------------------------------------------------
    # Business constraints
    # ------------------------------------------------------------
    @api.constrains("employee_id", "department_id")
    def _check_single_assignment(self):
        for rec in self:
            if rec.employee_id and rec.department_id:
                raise ValidationError("Một tài sản chỉ được gán cho Nhân viên hoặc Phòng ban (không được chọn cả hai).")

    @api.constrains("state", "employee_id", "department_id")
    def _check_assignment_when_in_use(self):
        for rec in self:
            if rec.state == "in_use" and not (rec.employee_id or rec.department_id):
                raise ValidationError("Tài sản ở trạng thái 'Đang sử dụng' phải được gán cho Nhân viên hoặc Phòng ban.")

    # ------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------
    @api.depends(
        "value",
        "depreciation_method",
        "depreciation_unit",
        "depreciation_years",
        "declining_factor",
        "depreciation_start_date",
    )
    def _compute_depreciation_values(self):
        """Compute depreciation using multiple simplified methods.

        Methods implemented (training/project-friendly):
        - linear: straight-line per period
        - declining: declining balance (double declining by default)
        - syd: sum-of-years-digits generalized by number of periods
        """
        today = fields.Date.context_today(self)
        if isinstance(today, str):
            today = fields.Date.from_string(today)

        for rec in self:
            value = rec.value or 0.0
            total_periods = int(rec.depreciation_years or 0)
            rec.depreciation_per_year = 0.0
            rec.accumulated_depreciation = 0.0
            rec.book_value = value

            if rec.depreciation_method == "none" or value <= 0.0 or total_periods <= 0:
                continue

            start = rec.depreciation_start_date or rec.in_service_date or rec.purchase_date
            if not start:
                continue
            if isinstance(start, str):
                start = fields.Date.from_string(start)

            # How many periods have elapsed since start?
            if today <= start:
                elapsed_periods = 0
            else:
                if rec.depreciation_unit == "month":
                    delta = relativedelta(today, start)
                    elapsed_periods = max(delta.years * 12 + delta.months, 0)
                else:
                    delta = relativedelta(today, start)
                    elapsed_periods = max(delta.years, 0)

            elapsed_periods = min(elapsed_periods, total_periods)
            if elapsed_periods <= 0:
                continue

            if rec.depreciation_method == "linear":
                per = value / float(total_periods)
                rec.depreciation_per_year = per
                accumulated = per * float(elapsed_periods)
                rec.accumulated_depreciation = min(accumulated, value)
                rec.book_value = max(value - rec.accumulated_depreciation, 0.0)
                continue

            if rec.depreciation_method == "syd":
                # Sum-of-years-digits generalized by number of periods
                denom = total_periods * (total_periods + 1) / 2.0
                if denom <= 0:
                    continue
                # depreciation of period i (1-based): remaining_periods / denom * value
                acc = 0.0
                for i in range(1, elapsed_periods + 1):
                    remaining = total_periods - i + 1
                    acc += value * (remaining / denom)
                rec.depreciation_per_year = value * (total_periods / denom)
                rec.accumulated_depreciation = min(acc, value)
                rec.book_value = max(value - rec.accumulated_depreciation, 0.0)
                continue

            if rec.depreciation_method == "declining":
                # Declining balance: each period depreciates by a constant rate on opening book value.
                factor = rec.declining_factor or 2.0
                rate = min(max(factor / float(total_periods), 0.0), 1.0)
                book = value
                acc = 0.0
                for _ in range(elapsed_periods):
                    dep = book * rate
                    dep = min(dep, book)
                    acc += dep
                    book -= dep
                    if book <= 0:
                        book = 0.0
                        break
                rec.depreciation_per_year = value * rate
                rec.accumulated_depreciation = min(acc, value)
                rec.book_value = max(book, 0.0)

    @api.depends("next_maintenance_date")
    def _compute_maintenance_overdue(self):
        today = fields.Date.context_today(self)
        if isinstance(today, str):
            today = fields.Date.from_string(today)
        for rec in self:
            if rec.next_maintenance_date:
                d = rec.next_maintenance_date
                if isinstance(d, str):
                    d = fields.Date.from_string(d)
                rec.maintenance_overdue = d < today
            else:
                rec.maintenance_overdue = False

    # ------------------------------------------------------------
    # Cron
    # ------------------------------------------------------------
    @api.model
    def _cron_update_maintenance_state(self):
        """If next_maintenance_date is overdue, automatically move asset to Maintenance state."""
        today = fields.Date.context_today(self)
        if isinstance(today, str):
            today = fields.Date.from_string(today)

        assets = self.search(
            [
                ("next_maintenance_date", "!=", False),
                ("next_maintenance_date", "<", today),
                ("state", "not in", ["maintenance", "broken"]),
                ("active", "=", True),
            ]
        )
        if assets:
            assets.write({"state": "maintenance"})

