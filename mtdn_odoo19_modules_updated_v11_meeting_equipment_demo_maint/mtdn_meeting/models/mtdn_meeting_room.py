# -*- coding: utf-8 -*-
from odoo import api, fields, models


class MtdnMeetingRoom(models.Model):
    _name = "mtdn.meeting.room"
    _description = "MTDN Meeting Room"
    _order = "code, name"

    code = fields.Char(string="Mã phòng", required=True, copy=False, index=True)
    name = fields.Char(string="Tên phòng", required=True, index=True)

    location = fields.Char(string="Vị trí", help="VD: Tầng 3 - Khu A")
    capacity = fields.Integer(string="Sức chứa", default=6)

    state = fields.Selection(
        selection=[
            ("available", "Sẵn sàng"),
            ("maintenance", "Bảo trì"),
        ],
        string="Trạng thái (quản lý)",
        required=True,
        default="available",
        index=True,
        help="Trạng thái quản lý thủ công. 'Đang sử dụng' được tính tự động dựa trên lịch đặt phòng.",
    )

    display_state = fields.Selection(
        selection=[
            ("available", "Sẵn sàng"),
            ("in_use", "Đang sử dụng"),
            ("maintenance", "Bảo trì"),
        ],
        string="Trạng thái",
        compute="_compute_display_state",
        store=False,
        readonly=True,
    )

    company_id = fields.Many2one(
        "res.company",
        string="Công ty",
        default=lambda self: self.env.company,
        required=True,
        index=True,
    )

    equipment_ids = fields.Many2many(
        "mtdn.asset",
        "mtdn_meeting_room_asset_rel",
        "room_id",
        "asset_id",
        string="Thiết bị trong phòng",
        domain="[('state','!=','broken')]",
        help="Liên kết trực tiếp với module Tài sản (mtdn.asset).",
    )

    equipment_type_ids = fields.Many2many(
        "mtdn.asset.equipment.type",
        string="Loại thiết bị có sẵn",
        compute="_compute_equipment_type_ids",
        help="Tự động tổng hợp từ các thiết bị (tài sản) gắn với phòng.",
    )

    active = fields.Boolean(default=True)

    booking_count = fields.Integer(string="Lịch đặt", compute="_compute_booking_count", store=False)

    def _compute_booking_count(self):
        Booking = self.env["mtdn.meeting.booking"]
        for rec in self:
            rec.booking_count = Booking.search_count([("room_id", "=", rec.id), ("state", "!=", "cancelled")])

    def action_view_bookings(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Lịch đặt phòng",
            "res_model": "mtdn.meeting.booking",
            "view_mode": "calendar,list,form",
            "domain": [("room_id", "=", self.id)],
            "context": {"default_room_id": self.id},
        }

    @api.depends("state")
    def _compute_display_state(self):
        """Compute live room state.

        - If room is in maintenance -> maintenance
        - Else if there is an active booking overlapping now -> in_use
        - Else -> available
        """
        now = fields.Datetime.now()
        Booking = self.env["mtdn.meeting.booking"]
        for rec in self:
            if rec.state == "maintenance":
                rec.display_state = "maintenance"
                continue

            busy = Booking.search_count(
                [
                    ("state", "!=", "cancelled"),
                    ("room_id", "=", rec.id),
                    ("start_datetime", "<=", now),
                    ("end_datetime", ">=", now),
                ]
            )
            rec.display_state = "in_use" if busy else "available"

    def _compute_equipment_type_ids(self):
        for rec in self:
            rec.equipment_type_ids = rec.equipment_ids.mapped("equipment_type_id")

    _sql_constraints = [
        ("mtdn_meeting_room_code_uniq", "unique(code)", "Mã phòng họp phải là duy nhất."),
    ]
