# -*- coding: utf-8 -*-

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class MtdnMeetingBookingTimeWizard(models.TransientModel):
    _name = "mtdn.meeting.booking.time.wizard"
    _description = "MTDN Booking Time Picker (Wizard)"

    request_id = fields.Many2one(
        "mtdn.meeting.room.request",
        string="Yêu cầu",
        required=True,
        ondelete="cascade",
    )
    room_id = fields.Many2one(
        "mtdn.meeting.room",
        string="Phòng",
        required=True,
        ondelete="restrict",
    )

    title = fields.Char(string="Tiêu đề", default="Cuộc họp")
    start_datetime = fields.Datetime(string="Bắt đầu", required=True, default=lambda self: fields.Datetime.now())
    end_datetime = fields.Datetime(string="Kết thúc", required=True)
    note = fields.Text(string="Ghi chú")

    host_id = fields.Many2one(
        "mtdn.employee",
        string="Chủ trì (Host)",
        required=True,
        ondelete="restrict",
        default=False,
    )

    participant_ids = fields.Many2many(
        "mtdn.employee",
        "mtdn_meeting_booking_time_wizard_employee_rel",
        "wizard_id",
        "employee_id",
        string="Thành phần tham gia",
    )

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        # Default host similar to booking model
        if "host_id" in fields_list and not vals.get("host_id"):
            emp = False
            if self.env.user.email:
                emp = self.env["mtdn.employee"].search([("email", "=", self.env.user.email)], limit=1)
            if not emp:
                emp = self.env["mtdn.employee"].search([], limit=1)
            if emp:
                vals["host_id"] = emp.id
        # Default duration 1 hour
        if "end_datetime" in fields_list:
            start = vals.get("start_datetime")
            if start and not vals.get("end_datetime"):
                vals["end_datetime"] = fields.Datetime.to_string(
                    fields.Datetime.from_string(start) + relativedelta(hours=1)
                )
        return vals

    @api.constrains("start_datetime", "end_datetime")
    def _check_time_range(self):
        for rec in self:
            if rec.end_datetime and rec.start_datetime and rec.end_datetime <= rec.start_datetime:
                raise ValidationError("Thời gian kết thúc phải lớn hơn thời gian bắt đầu.")

    @api.constrains("participant_ids")
    def _check_participants_required(self):
        for rec in self:
            if not rec.participant_ids:
                raise ValidationError("Vui lòng chọn ít nhất 1 thành phần tham gia.")

    def action_confirm(self):
        self.ensure_one()

        # Store the chosen time back into the request for audit/UX.
        self.request_id.write(
            {
                "start_datetime": self.start_datetime,
                "end_datetime": self.end_datetime,
                "title": self.title or self.request_id.title,
                "note": self.note or self.request_id.note,
            }
        )

        return self.request_id._create_booking_and_open_calendar(
            room=self.room_id,
            start=self.start_datetime,
            end=self.end_datetime,
            host_id=self.host_id.id,
            participant_ids=self.participant_ids.ids,
        )
