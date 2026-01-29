# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError

import re
import json
import urllib.request
import urllib.error
from datetime import datetime, timedelta

import pytz


class MtdnMeetingRoomRequest(models.TransientModel):
    _name = "mtdn.meeting.room.request"
    _description = "MTDN Meeting Room Request (Wizard)"

    title = fields.Char(string="Tiêu đề", default="Cuộc họp")
    start_datetime = fields.Datetime(string="Bắt đầu")
    end_datetime = fields.Datetime(string="Kết thúc")
    attendee_count = fields.Integer(string="Số người (dự kiến)", default=0)
    location_keyword = fields.Char(string="Vị trí / Từ khóa")

    required_equipment_type_ids = fields.Many2many(
        "mtdn.asset.equipment.type",
        "mtdn_meeting_request_equipment_type_rel",
        "request_id",
        "equipment_type_id",
        string="Thiết bị cần có",
        help="Chọn các loại thiết bị bắt buộc. Hệ thống sẽ lọc các phòng có đầy đủ các loại thiết bị này.",
    )

    note = fields.Text(string="Ghi chú")

    # AI assistant (Gemini) - natural language request
    ai_request_text = fields.Text(
        string="Yêu cầu bằng tiếng Việt (AI)",
        help="Ví dụ: 'Mai 9h-10h họp 8 người, cần TV và zoom'. Bấm 'Phân tích bằng AI' để tự điền form.",
    )
    ai_parse_result = fields.Text(string="Kết quả AI (JSON)", readonly=True, copy=False)
    ai_parse_error = fields.Char(string="Lỗi AI", readonly=True, copy=False)


    # Use One2many lines instead of a bare Many2many list, so we can provide a
    # clear "Chọn" action for each suggested room (professional UX).
    line_ids = fields.One2many(
        "mtdn.meeting.room.request.line",
        "request_id",
        string="Kết quả gợi ý",
        readonly=True,
        copy=False,
    )


    # AI ranking & alternatives (meaningful assistant)
    ai_rank_note = fields.Text(string="Gợi ý AI", readonly=True, copy=False)
    alt_line_ids = fields.One2many(
        "mtdn.meeting.room.request.alt",
        "request_id",
        string="Gợi ý lịch thay thế (AI)",
        readonly=True,
        copy=False,
    )

    # Convenience compute for domains (selected_room_id dropdown)
    result_room_ids = fields.Many2many(
        "mtdn.meeting.room",
        compute="_compute_result_rooms",
        string="Phòng phù hợp",
        readonly=True,
    )

    selected_room_id = fields.Many2one(
        "mtdn.meeting.room",
        string="Phòng đã chọn",
        domain="[('id','in', result_room_ids)]",
    )

    @api.depends("line_ids", "line_ids.room_id")
    def _compute_result_rooms(self):
        for rec in self:
            rec.result_room_ids = rec.line_ids.mapped("room_id")

    @api.constrains("start_datetime", "end_datetime")
    def _check_time_range(self):
        for rec in self:
            if rec.start_datetime and rec.end_datetime and rec.end_datetime <= rec.start_datetime:
                raise ValidationError("Thời gian kết thúc phải lớn hơn thời gian bắt đầu.")


    def _ai_local_to_utc(self, dt_str):
        """Convert a local datetime string (user tz) -> naive UTC datetime."""
        if not dt_str:
            return False
        s = (dt_str or "").strip()
        # Accept "YYYY-MM-DD HH:MM[:SS]" or ISO "YYYY-MM-DDTHH:MM[:SS]"
        s = s.replace("T", " ")
        fmt_candidates = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]
        dt_local = None
        for fmt in fmt_candidates:
            try:
                dt_local = datetime.strptime(s, fmt)
                break
            except Exception:
                continue
        if not dt_local:
            raise ValidationError("AI trả về thời gian không đúng định dạng: %s" % dt_str)

        tz_name = self.env.user.tz or "Asia/Bangkok"
        tz = pytz.timezone(tz_name)
        dt_local = tz.localize(dt_local, is_dst=None)
        dt_utc = dt_local.astimezone(pytz.UTC).replace(tzinfo=None)
        return dt_utc

    def _ai_equipment_types_from_tags(self, tags):
        """Map canonical tags -> equipment type codes."""
        tags = [t.strip().lower() for t in (tags or []) if t and str(t).strip()]
        codes = set()

        # Canonical tags
        for t in tags:
            if t in ("tv", "screen", "monitor"):
                codes.add("TV")
            elif t in ("projector", "may_chieu"):
                codes.add("PRJ")
            elif t in ("microphone", "mic", "micro"):
                codes.add("MIC")
            elif t in ("speaker", "loa"):
                codes.add("SPK")
            elif t in ("camera", "cam"):
                codes.add("CAM")
            elif t in ("video_conference", "zoom", "meet", "teams", "online"):
                # For online meetings, require core set (camera + mic + speaker)
                codes.update(["CAM", "MIC", "SPK"])

        if not codes:
            return self.env["mtdn.asset.equipment.type"]

        return self.env["mtdn.asset.equipment.type"].search([("code", "in", list(codes)), ("active", "=", True)])

    def _ai_build_prompt(self):
        self.ensure_one()

        config = self.env["mtdn.meeting.ai.config"].sudo().get_active_config()
        if not config or not config.api_key:
            raise ValidationError("Chưa cấu hình Gemini API Key. Vào menu 'Cấu hình AI (Gemini)' để nhập key.")

        tz_name = self.env.user.tz or "Asia/Bangkok"
        now_utc = datetime.utcnow().replace(tzinfo=pytz.UTC)
        now_local = now_utc.astimezone(pytz.timezone(tz_name))

        # Allowed equipment tags (canonical)
        allowed_tags = [
            "tv",
            "projector",
            "microphone",
            "speaker",
            "camera",
            "video_conference"
        ]

        prompt = f"""Bạn là trợ lý trích xuất thông tin đặt phòng họp từ câu tiếng Việt.
Nhiệm vụ: Đọc yêu cầu người dùng và trả về JSON theo schema đã cung cấp.

Quy tắc thời gian:
- Timezone hiện tại: {tz_name}
- Thời điểm hiện tại (để hiểu 'hôm nay/mai/tuần này'): {now_local.strftime('%Y-%m-%d %H:%M:%S')}
- Các cụm như 'hôm nay', 'mai', 'chiều', 'sáng', 'thứ 2..CN', 'thứ 6 tuần này' phải được quy đổi ra ngày cụ thể.
- Trả start/end theo định dạng: YYYY-MM-DD HH:MM:SS (24h). Không kèm timezone.

Quy tắc thiết bị:
- Chỉ dùng các tag trong danh sách cho trường equipment_tags: {', '.join(allowed_tags)}
- Nếu người dùng nói 'zoom/meet/teams/họp online' thì dùng tag: video_conference.

Yêu cầu người dùng:
{(self.ai_request_text or '').strip()}
"""
        return config, prompt

    def _ai_call_gemini(self, api_key, model_name, prompt, schema):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"

        payload = {
            "contents": [
                {"parts": [{"text": prompt}]}
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": schema,
            },
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode("utf-8")
            except Exception:
                err_body = str(e)
            raise ValidationError(f"Lỗi gọi Gemini API: HTTP {e.code}. {err_body}")
        except Exception as e:
            raise ValidationError(f"Lỗi gọi Gemini API: {e}")

        try:
            resp_json = json.loads(raw)
        except Exception:
            raise ValidationError("Gemini API trả về dữ liệu không phải JSON: %s" % raw[:200])

        # Extract model text (should be a JSON string due to responseMimeType)
        try:
            text = resp_json["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            raise ValidationError("Không đọc được kết quả từ Gemini. Response: %s" % raw[:500])

        return text

    def action_ai_parse(self):
        """Parse Vietnamese natural language -> autofill request wizard fields."""
        self.ensure_one()

        self.ai_parse_error = False

        if not (self.ai_request_text or "").strip():
            raise ValidationError("Vui lòng nhập yêu cầu bằng tiếng Việt để AI phân tích.")

        # JSON Schema for structured output
        schema = {
            "type": "object",
            "properties": {
                "title": {"type": ["string", "null"], "description": "Tiêu đề cuộc họp (nếu có)."},
                "start": {"type": "string", "description": "Thời gian bắt đầu, định dạng YYYY-MM-DD HH:MM:SS."},
                "end": {"type": "string", "description": "Thời gian kết thúc, định dạng YYYY-MM-DD HH:MM:SS."},
                "attendee_count": {"type": ["integer", "null"], "description": "Số người tham gia (dự kiến)."},
                "equipment_tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Danh sách tag thiết bị theo danh sách cho phép."
                },
                "location_keyword": {"type": ["string", "null"], "description": "Từ khóa vị trí (nếu người dùng nói)."},
                "note": {"type": ["string", "null"], "description": "Ghi chú thêm (nếu có)."},
            },
            "required": ["start", "end", "equipment_tags"],
            "additionalProperties": False,
        }

        config, prompt = self._ai_build_prompt()
        ai_text = self._ai_call_gemini(config.api_key, config.model_name, prompt, schema)

        # Parse JSON string returned by model
        try:
            parsed = json.loads(ai_text)
        except Exception:
            # best effort: extract the first JSON object in text
            m = re.search(r"\{.*\}", ai_text, re.S)
            if m:
                parsed = json.loads(m.group(0))
            else:
                self.ai_parse_error = "AI trả về không phải JSON hợp lệ."
                self.ai_parse_result = ai_text
                raise ValidationError(self.ai_parse_error)

        self.ai_parse_result = json.dumps(parsed, ensure_ascii=False, indent=2)

        try:
            start_utc = self._ai_local_to_utc(parsed.get("start"))
            end_utc = self._ai_local_to_utc(parsed.get("end"))
        except Exception as e:
            self.ai_parse_error = str(e)
            raise

        # Apply to wizard fields
        if parsed.get("title"):
            self.title = parsed.get("title")

        if parsed.get("attendee_count") is not None:
            self.attendee_count = int(parsed.get("attendee_count") or 0)

        if parsed.get("location_keyword"):
            self.location_keyword = parsed.get("location_keyword")

        if parsed.get("note"):
            self.note = parsed.get("note")

        self.start_datetime = start_utc
        self.end_datetime = end_utc

        # Equipment mapping
        tags = parsed.get("equipment_tags") or []
        eq_types = self._ai_equipment_types_from_tags(tags)
        if eq_types:
            self.required_equipment_type_ids = [(6, 0, eq_types.ids)]

        return {
            "type": "ir.actions.act_window",
            "res_model": "mtdn.meeting.room.request",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }


    def _ai_rank_rooms(self, rooms):
        """Ask Gemini to rank candidate rooms. Fallback to deterministic scoring if AI fails."""
        self.ensure_one()
        self.ai_rank_note = False

        # Clear existing AI fields on lines
        for ln in self.line_ids:
            ln.ai_rank = False
            ln.ai_reason = False

        if not rooms:
            return

        # Build candidates payload (limit for prompt size)
        candidates = []
        for r in rooms[:25]:
            candidates.append({
                "room_id": r.id,
                "code": r.code,
                "name": r.name,
                "location": r.location or "",
                "capacity": r.capacity,
                "equipment": r.equipment_type_ids.mapped("name"),
            })

        requirements = {
            "attendee_count": int(self.attendee_count or 0),
            "location_keyword": (self.location_keyword or "").strip(),
            "required_equipment": self.required_equipment_type_ids.mapped("name"),
            "start": self.start_datetime and fields.Datetime.to_string(self.start_datetime) or "",
            "end": self.end_datetime and fields.Datetime.to_string(self.end_datetime) or "",
        }

        # JSON Schema for structured ranking
        schema = {
            "type": "object",
            "properties": {
                "recommendations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "room_id": {"type": "integer"},
                            "rank": {"type": "integer"},
                            "reason": {"type": "string"},
                        },
                        "required": ["room_id", "rank", "reason"],
                        "additionalProperties": False,
                    },
                },
                "note": {"type": ["string", "null"]},
            },
            "required": ["recommendations"],
            "additionalProperties": False,
        }

        # Prompt
        prompt = (
            "Bạn là trợ lý xếp hạng phòng họp.\n"
            "Đầu vào gồm nhu cầu cuộc họp và danh sách phòng hợp lệ (đã qua kiểm tra trùng lịch/sức chứa/thiết bị bắt buộc).\n"
            "Hãy chọn ra TOP 3 phòng tốt nhất và giải thích ngắn gọn cho từng phòng.\n"
            "Tiêu chí ưu tiên: (1) Phòng vừa đủ sức chứa (ít lãng phí), (2) khớp thiết bị, (3) khớp từ khóa vị trí nếu có.\n"
            "Chỉ trả về JSON theo schema.\n\n"
            f"Nhu cầu: {json.dumps(requirements, ensure_ascii=False)}\n"
            f"Phòng hợp lệ: {json.dumps(candidates, ensure_ascii=False)}"
        )

        # Try AI
        try:
            config = self.env["mtdn.meeting.ai.config"].sudo().get_active_config()
            if config and config.api_key:
                ai_text = self._ai_call_gemini(config.api_key, config.model_name, prompt, schema)
                data = json.loads(ai_text)
                recs = data.get("recommendations") or []
                note = data.get("note")
                if note:
                    self.ai_rank_note = note
                # apply to lines
                by_room = {int(x.get("room_id")): x for x in recs if x.get("room_id")}
                for ln in self.line_ids:
                    item = by_room.get(ln.room_id.id)
                    if item:
                        ln.ai_rank = int(item.get("rank") or 0)
                        ln.ai_reason = (item.get("reason") or "")[:200]
                return
        except Exception:
            # Silent fallback to deterministic scoring
            pass

        # Fallback scoring (deterministic)
        def score(room):
            cap = room.capacity or 0
            need = int(self.attendee_count or 0)
            cap_gap = max(cap - need, 0)
            kw = (self.location_keyword or "").strip().lower()
            kw_hit = 1 if kw and ((room.location or "").lower().find(kw) >= 0 or (room.name or "").lower().find(kw) >= 0) else 0
            # smaller gap is better, keyword hit bonus
            return (kw_hit * 1000) - cap_gap

        ranked = sorted(rooms, key=score, reverse=True)[:3]
        for idx, r in enumerate(ranked, start=1):
            ln = self.line_ids.filtered(lambda l: l.room_id.id == r.id)[:1]
            if ln:
                ln.ai_rank = idx
                ln.ai_reason = "Phù hợp theo sức chứa & thiết bị."

    def _ai_suggest_alternatives(self):
        """When no room matches, propose alternative time slots near the requested time."""
        self.ensure_one()
        self.alt_line_ids = [(5, 0, 0)]

        if not (self.start_datetime and self.end_datetime):
            return

        # Generate candidate slots: +/- 30, 60, 90, 120 minutes; plus next day same time
        duration_minutes = int((self.end_datetime - self.start_datetime).total_seconds() / 60.0)
        if duration_minutes <= 0:
            return

        offsets = [-120, -90, -60, -30, 30, 60, 90, 120]
        slot_candidates = []
        for off in offsets:
            s = self.start_datetime + timedelta(minutes=off)
            e = s + timedelta(minutes=duration_minutes)
            slot_candidates.append((s, e))
        # next day same time
        slot_candidates.append((self.start_datetime + timedelta(days=1), self.end_datetime + timedelta(days=1)))

        # Deduplicate by start
        seen=set()
        slots=[]
        for s,e in slot_candidates:
            key=fields.Datetime.to_string(s)
            if key in seen:
                continue
            seen.add(key)
            # do not suggest past
            if s < fields.Datetime.now():
                continue
            slots.append((s,e))
        slots = slots[:12]

        # Build base room domain (same as action_search_rooms, but without time constraint)
        room_domain = [("active", "=", True), ("state", "=", "available")]
        if self.attendee_count and self.attendee_count > 0:
            room_domain.append(("capacity", ">=", self.attendee_count))
        if self.location_keyword:
            kw = (self.location_keyword or "").strip()
            if kw:
                room_domain += ["|", ("location", "ilike", kw), ("name", "ilike", kw)]
        rooms_base = self.env["mtdn.meeting.room"].search(room_domain)
        rooms_base = rooms_base.filtered(self._match_equipment_types)

        options=[]
        for s,e in slots:
            busy_domain = [
                ("state", "!=", "cancelled"),
                ("start_datetime", "<", e),
                ("end_datetime", ">", s),
            ]
            busy_room_ids = set(self.env["mtdn.meeting.booking"].search(busy_domain).mapped("room_id").ids)
            free_rooms = rooms_base.filtered(lambda r: r.id not in busy_room_ids)
            if free_rooms:
                options.append({
                    "start": fields.Datetime.to_string(s),
                    "end": fields.Datetime.to_string(e),
                    "available_rooms_count": len(free_rooms),
                })
        if not options:
            return

        # JSON schema
        schema = {
            "type": "object",
            "properties": {
                "alternatives": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "start": {"type": "string"},
                            "end": {"type": "string"},
                            "reason": {"type": "string"},
                        },
                        "required": ["start", "end", "reason"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["alternatives"],
            "additionalProperties": False,
        }

        prompt = (
            "Bạn là trợ lý đề xuất lịch thay thế khi không còn phòng phù hợp.\n"
            "Từ danh sách lựa chọn thời gian có phòng trống, hãy chọn 3 lựa chọn tốt nhất.\n"
            "Tiêu chí: gần thời gian yêu cầu nhất, nhiều phòng trống hơn, phù hợp nhu cầu.\n"
            "Chỉ trả về JSON theo schema.\n\n"
            f"Thời gian yêu cầu ban đầu: {fields.Datetime.to_string(self.start_datetime)} - {fields.Datetime.to_string(self.end_datetime)}\n"
            f"Các lựa chọn: {json.dumps(options, ensure_ascii=False)}"
        )

        alts=[]
        try:
            config = self.env["mtdn.meeting.ai.config"].sudo().get_active_config()
            if config and config.api_key:
                ai_text = self._ai_call_gemini(config.api_key, config.model_name, prompt, schema)
                data = json.loads(ai_text)
                alts = data.get("alternatives") or []
        except Exception:
            alts = []

        if not alts:
            # fallback: pick first 3 by closeness to original start
            orig = self.start_datetime
            def dist(opt):
                s = fields.Datetime.from_string(opt["start"])
                return abs((s - orig).total_seconds())
            alts = sorted(options, key=dist)[:3]
            for o in alts:
                o["reason"] = "Gợi ý theo lịch gần nhất còn phòng trống."

        # create alt lines
        lines=[]
        for o in alts[:3]:
            try:
                s = fields.Datetime.from_string(o["start"])
                e = fields.Datetime.from_string(o["end"])
            except Exception:
                continue
            lines.append((0,0,{
                "start_datetime": s,
                "end_datetime": e,
                "reason": (o.get("reason") or "")[:200],
            }))
        self.alt_line_ids = lines

    def _match_equipment_types(self, room):
        """Match rooms by required equipment types (professional, data-driven)."""
        if not self.required_equipment_type_ids:
            return True

        room_type_ids = set(room.equipment_ids.mapped("equipment_type_id").ids)
        required_ids = set(self.required_equipment_type_ids.ids)
        # Room must contain all required equipment types
        return required_ids.issubset(room_type_ids)

    def action_search_rooms(self):
        self.ensure_one()

        # Base domain
        domain = [("active", "=", True), ("state", "=", "available")]

        if self.attendee_count and self.attendee_count > 0:
            domain.append(("capacity", ">=", self.attendee_count))

        if self.location_keyword:
            kw = (self.location_keyword or "").strip()
            if kw:
                domain += ["|", ("location", "ilike", kw), ("name", "ilike", kw)]

        rooms = self.env["mtdn.meeting.room"].search(domain)

        # Time availability filter (only if both start/end are provided)
        if self.start_datetime and self.end_datetime:
            if self.end_datetime <= self.start_datetime:
                raise ValidationError("Thời gian kết thúc phải lớn hơn thời gian bắt đầu.")

            busy_domain = [
                ("state", "!=", "cancelled"),
                ("start_datetime", "<", self.end_datetime),
                ("end_datetime", ">", self.start_datetime),
            ]
            busy_room_ids = self.env["mtdn.meeting.booking"].search(busy_domain).mapped("room_id").ids
            rooms = rooms.filtered(lambda r: r.id not in busy_room_ids)

        # Equipment type matching
        rooms = rooms.filtered(self._match_equipment_types)

        # Reset previous results
        self.line_ids = [(5, 0, 0)]

        # Create result lines
        lines = []
        # reset AI alternatives
        self.alt_line_ids = [(5, 0, 0)]

        for room in rooms:
            lines.append(
                (
                    0,
                    0,
                    {
                        "room_id": room.id,
                    },
                )
            )
        self.line_ids = lines

        # AI ranking / alternatives (meaningful assistant)
        if rooms:
            self._ai_rank_rooms(rooms)
        else:
            self._ai_suggest_alternatives()

        # Keep selected room valid
        if self.selected_room_id and self.selected_room_id not in rooms:
            self.selected_room_id = False

        return {
            "type": "ir.actions.act_window",
            "res_model": "mtdn.meeting.room.request",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_create_booking(self):
        self.ensure_one()
        if not self.selected_room_id:
            raise ValidationError("Vui lòng chọn 1 phòng trong danh sách gợi ý.")

        # Always force user to input the missing meeting details (host + participants)
        # after selecting a suitable room (per requirement).
        return {
            "type": "ir.actions.act_window",
            "name": "Thông tin đặt phòng",
            "res_model": "mtdn.meeting.booking.time.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_request_id": self.id,
                "default_room_id": self.selected_room_id.id,
                "default_title": self.title or "Cuộc họp",
                "default_note": self.note,
                "default_start_datetime": self.start_datetime,
                "default_end_datetime": self.end_datetime,
            },
        }

    def _create_booking_and_open_calendar(self, room, start, end, host_id=False, participant_ids=None):
        """Create booking and redirect to the Booking calendar so users see it immediately."""
        self.ensure_one()

        participant_ids = participant_ids or []

        if not host_id:
            # Best-effort default host if wizard didn't provide
            host_emp = False
            if self.env.user.email:
                host_emp = self.env["mtdn.employee"].search([("email", "=", self.env.user.email)], limit=1)
            if not host_emp:
                host_emp = self.env["mtdn.employee"].search([], limit=1)
            host_id = host_emp.id if host_emp else False

        booking = self.env["mtdn.meeting.booking"].create(
            {
                "name": self.title or "Cuộc họp",
                "room_id": room.id,
                "start_datetime": start,
                "end_datetime": end,
                "host_id": host_id,
                "participant_ids": [(6, 0, participant_ids)],
                # show equipment of the selected room by default
                "equipment_ids": [(6, 0, room.equipment_ids.ids)],
                "required_equipment_type_ids": [(6, 0, self.required_equipment_type_ids.ids)],
                "note": self.note,
                "state": "draft",
            }
        )

        # Open booking calendar (WITHOUT filtering by the new booking), so users see all existing bookings.
        action = self.env.ref("mtdn_meeting.action_mtdn_meeting_booking").read()[0]
        action.update({"context": dict(self.env.context, default_room_id=room.id)})
        return action
