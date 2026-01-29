# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class MtdnMeetingRoom(models.Model):
    _inherit = "mtdn.meeting.room"

    maintenance_request_count = fields.Integer(
        string="Phiếu bảo trì",
        compute="_compute_maintenance_request_count",
        store=False,
    )

    def _compute_maintenance_request_count(self):
        Req = self.env["mtdn.maintenance.request"]
        for rec in self:
            rec.maintenance_request_count = Req.search_count(
                [("request_for", "=", "room"), ("room_id", "=", rec.id)]
            )

    def action_view_maintenance_requests(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Phiếu bảo trì",
            "res_model": "mtdn.maintenance.request",
            "view_mode": "list,form",
            "domain": [("request_for", "=", "room"), ("room_id", "=", self.id)],
            "context": {"default_request_for": "room", "default_room_id": self.id},
        }

    @api.depends("state")
    def _compute_display_state(self):
        """Extend live room state: consider maintenance downtime requests."""
        now = fields.Datetime.now()
        Booking = self.env["mtdn.meeting.booking"]
        Req = self.env["mtdn.maintenance.request"]
        for rec in self:
            # Manual maintenance always wins
            if rec.state == "maintenance":
                rec.display_state = "maintenance"
                continue

            # Maintenance downtime active now
            active_maint = Req.search_count(
                [
                    ("request_for", "=", "room"),
                    ("room_id", "=", rec.id),
                    ("state", "in", ("submitted", "in_progress")),
                    ("start_datetime", "<=", now),
                    ("end_datetime", ">=", now),
                ]
            )
            if active_maint:
                rec.display_state = "maintenance"
                continue

            # Booking overlap -> in use
            busy = Booking.search_count(
                [
                    ("state", "!=", "cancelled"),
                    ("room_id", "=", rec.id),
                    ("start_datetime", "<=", now),
                    ("end_datetime", ">=", now),
                ]
            )
            rec.display_state = "in_use" if busy else "available"


class MtdnMeetingBooking(models.Model):
    _inherit = "mtdn.meeting.booking"

    @api.constrains("room_id", "start_datetime", "end_datetime", "state")
    def _check_overlap_with_room_downtime(self):
        Req = self.env["mtdn.maintenance.request"]
        for rec in self:
            if not rec.room_id or not rec.start_datetime or not rec.end_datetime:
                continue
            if rec.state == "cancelled":
                continue
            domain = [
                ("request_for", "=", "room"),
                ("room_id", "=", rec.room_id.id),
                ("state", "in", ("submitted", "in_progress")),
                ("start_datetime", "<", rec.end_datetime),
                ("end_datetime", ">", rec.start_datetime),
            ]
            if Req.search_count(domain):
                raise ValidationError(
                    "Phòng họp đang có downtime bảo trì trong khoảng thời gian này. "
                    "Vui lòng chọn phòng khác hoặc đổi thời gian."
                )

    @api.onchange("start_datetime", "end_datetime")
    def _onchange_time_domain_room(self):
        """Extend room availability domain: exclude rooms in downtime maintenance."""
        res = super()._onchange_time_domain_room()
        for rec in self:
            if not rec.start_datetime or not rec.end_datetime:
                continue
            if rec.end_datetime <= rec.start_datetime:
                continue

            maint_domain = [
                ("request_for", "=", "room"),
                ("state", "in", ("submitted", "in_progress")),
                ("start_datetime", "<", rec.end_datetime),
                ("end_datetime", ">", rec.start_datetime),
            ]
            maint_room_ids = self.env["mtdn.maintenance.request"].search(maint_domain).mapped("room_id").ids

            if res and isinstance(res, dict) and res.get("domain") and res["domain"].get("room_id"):
                # Append to existing domain coming from super()
                res["domain"]["room_id"].append(("id", "not in", maint_room_ids))
            else:
                res = res or {}
                res.setdefault("domain", {})
                res["domain"]["room_id"] = [("id", "not in", maint_room_ids), ("state", "=", "available")]
        return res


class MtdnMeetingRoomRequestWizard(models.TransientModel):
    _inherit = "mtdn.meeting.room.request"

    def action_search_rooms(self):
        """Keep original flow, but remove rooms that have downtime maintenance overlap."""
        self.ensure_one()
        res = super().action_search_rooms()

        if self.start_datetime and self.end_datetime and self.line_ids:
            maint_domain = [
                ("request_for", "=", "room"),
                ("state", "in", ("submitted", "in_progress")),
                ("start_datetime", "<", self.end_datetime),
                ("end_datetime", ">", self.start_datetime),
            ]
            maint_room_ids = set(self.env["mtdn.maintenance.request"].search(maint_domain).mapped("room_id").ids)

            remove_lines = self.line_ids.filtered(lambda l: l.room_id.id in maint_room_ids)
            if remove_lines:
                remove_lines.unlink()

            # If all rooms got removed by downtime -> suggest alternatives
            if not self.line_ids and hasattr(self, "_ai_suggest_alternatives"):
                try:
                    self._ai_suggest_alternatives()
                except Exception:
                    pass

            # Re-rank if AI helper exists
            if self.line_ids and hasattr(self, "_ai_rank_rooms"):
                try:
                    self._ai_rank_rooms()
                except Exception:
                    pass

        return res
