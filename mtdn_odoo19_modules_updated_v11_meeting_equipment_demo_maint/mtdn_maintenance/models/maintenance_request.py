# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class MtdnMaintenanceRequest(models.Model):
    _name = "mtdn.maintenance.request"
    _description = "Maintenance Request (Room/Asset)"
    _order = "request_date desc, id desc"

    name = fields.Char(string="Mã phiếu", required=True, copy=False, default="New", index=True)

    request_for = fields.Selection(
        selection=[("room", "Phòng họp"), ("asset", "Tài sản/thiết bị")],
        string="Đối tượng bảo trì",
        required=True,
        default="room",
        index=True,
    )

    room_id = fields.Many2one(
        "mtdn.meeting.room",
        string="Phòng họp",
        ondelete="restrict",
        index=True,
    )
    asset_id = fields.Many2one(
        "mtdn.asset",
        string="Tài sản/thiết bị",
        ondelete="restrict",
        index=True,
    )

    category_id = fields.Many2one(
        "mtdn.maintenance.category",
        string="Loại sự cố",
        ondelete="set null",
        index=True,
    )
    team_id = fields.Many2one(
        "mtdn.maintenance.team",
        string="Đội xử lý",
        ondelete="set null",
        index=True,
    )

    priority = fields.Selection(
        selection=[("0", "Thấp"), ("1", "Trung bình"), ("2", "Cao"), ("3", "Khẩn cấp")],
        string="Mức độ",
        default="1",
        required=True,
        index=True,
    )

    request_date = fields.Datetime(string="Ngày tạo", default=fields.Datetime.now, required=True, index=True)
    requested_by = fields.Many2one("res.users", string="Người báo", default=lambda self: self.env.user, required=True)

    assigned_user_id = fields.Many2one("res.users", string="Người xử lý", ondelete="set null", index=True)

    # Downtime window (when this maintenance blocks booking/usage)
    start_datetime = fields.Datetime(string="Bắt đầu downtime")
    end_datetime = fields.Datetime(string="Kết thúc downtime")

    description = fields.Text(string="Mô tả sự cố / yêu cầu")
    resolution = fields.Text(string="Kết quả xử lý")

    currency_id = fields.Many2one(
        "res.currency",
        string="Tiền tệ",
        default=lambda self: self.env.company.currency_id,
        required=True,
    )
    cost = fields.Monetary(string="Chi phí", currency_field="currency_id")

    state = fields.Selection(
        selection=[
            ("draft", "Nháp"),
            ("submitted", "Đã gửi"),
            ("in_progress", "Đang xử lý"),
            ("done", "Hoàn tất"),
            ("cancelled", "Hủy"),
        ],
        string="Trạng thái",
        required=True,
        default="draft",
        index=True,
    )

    company_id = fields.Many2one("res.company", string="Công ty", default=lambda self: self.env.company, index=True)

    # Store previous states to allow safe restoration when maintenance finishes
    previous_room_state = fields.Selection(related="room_id.state", string="(Hidden)", readonly=True)
    previous_asset_state = fields.Selection(related="asset_id.state", string="(Hidden)", readonly=True)

    is_active_downtime = fields.Boolean(string="Đang downtime", compute="_compute_is_active_downtime", store=False)

    @api.depends("state", "start_datetime", "end_datetime")
    def _compute_is_active_downtime(self):
        now = fields.Datetime.now()
        for rec in self:
            if rec.state in ("submitted", "in_progress") and rec.start_datetime and rec.end_datetime:
                rec.is_active_downtime = rec.start_datetime <= now <= rec.end_datetime
            else:
                rec.is_active_downtime = False

    # ------------------------------------------------------------
    # Create / constraints
    # ------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"]
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = seq.next_by_code("mtdn.maintenance.request") or "New"
        return super().create(vals_list)

    @api.constrains("request_for", "room_id", "asset_id")
    def _check_target_required(self):
        for rec in self:
            if rec.request_for == "room" and not rec.room_id:
                raise ValidationError("Vui lòng chọn Phòng họp.")
            if rec.request_for == "asset" and not rec.asset_id:
                raise ValidationError("Vui lòng chọn Tài sản/thiết bị.")

    @api.constrains("start_datetime", "end_datetime")
    def _check_downtime_range(self):
        for rec in self:
            if rec.start_datetime and rec.end_datetime and rec.end_datetime <= rec.start_datetime:
                raise ValidationError("Downtime: Thời gian kết thúc phải lớn hơn thời gian bắt đầu.")

    # ------------------------------------------------------------
    # Overlap helpers
    # ------------------------------------------------------------
    @api.model
    def _overlap_domain(self, start_dt, end_dt):
        return [
            ("state", "in", ("submitted", "in_progress")),
            ("start_datetime", "<", end_dt),
            ("end_datetime", ">", start_dt),
        ]

    def _find_overlaps_for_room(self, room_id, start_dt, end_dt, exclude_id=None):
        domain = self._overlap_domain(start_dt, end_dt) + [("request_for", "=", "room"), ("room_id", "=", room_id)]
        if exclude_id:
            domain.append(("id", "!=", exclude_id))
        return self.search(domain)

    def _find_overlaps_for_asset(self, asset_id, start_dt, end_dt, exclude_id=None):
        domain = self._overlap_domain(start_dt, end_dt) + [("request_for", "=", "asset"), ("asset_id", "=", asset_id)]
        if exclude_id:
            domain.append(("id", "!=", exclude_id))
        return self.search(domain)

    @api.constrains("request_for", "room_id", "asset_id", "start_datetime", "end_datetime", "state")
    def _check_overlap_with_other_maintenance(self):
        for rec in self:
            if rec.state not in ("submitted", "in_progress"):
                continue
            if not (rec.start_datetime and rec.end_datetime):
                continue

            if rec.request_for == "room" and rec.room_id:
                if rec._find_overlaps_for_room(rec.room_id.id, rec.start_datetime, rec.end_datetime, exclude_id=rec.id):
                    raise ValidationError("Đã có phiếu bảo trì khác trùng downtime cho phòng này.")
            if rec.request_for == "asset" and rec.asset_id:
                if rec._find_overlaps_for_asset(rec.asset_id.id, rec.start_datetime, rec.end_datetime, exclude_id=rec.id):
                    raise ValidationError("Đã có phiếu bảo trì khác trùng downtime cho tài sản này.")

    # ------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------
    def action_submit(self):
        self.write({"state": "submitted"})

    def action_start(self):
        """Mark as in progress. Optionally switch room/asset state to maintenance for visibility."""
        for rec in self:
            rec.state = "in_progress"
            if rec.request_for == "room" and rec.room_id:
                rec.room_id.state = "maintenance"
            if rec.request_for == "asset" and rec.asset_id:
                rec.asset_id.state = "maintenance"

    def action_done(self):
        for rec in self:
            rec.state = "done"
            # Restore to available only if currently maintenance (best-effort)
            if rec.request_for == "room" and rec.room_id and rec.room_id.state == "maintenance":
                rec.room_id.state = "available"
            if rec.request_for == "asset" and rec.asset_id and rec.asset_id.state == "maintenance":
                rec.asset_id.state = "available"

    def action_cancel(self):
        for rec in self:
            rec.state = "cancelled"
            if rec.request_for == "room" and rec.room_id and rec.room_id.state == "maintenance":
                rec.room_id.state = "available"
            if rec.request_for == "asset" and rec.asset_id and rec.asset_id.state == "maintenance":
                rec.asset_id.state = "available"

    def action_set_draft(self):
        self.write({"state": "draft"})
