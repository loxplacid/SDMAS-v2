MSG_TYPE_ANNOUNCEMENT = "announcement"
MSG_TYPE_TARGETED = "targeted"
MSG_TYPE_CLASS = "class"
MSG_TYPE_SECTION = "section"
MSG_TYPE_PARENT = "parent"
MSG_TYPE_TEACHER = "teacher"
MSG_TYPE_STAFF = "staff"

MESSAGE_TYPES = [
    MSG_TYPE_ANNOUNCEMENT,
    MSG_TYPE_TARGETED,
    MSG_TYPE_CLASS,
    MSG_TYPE_SECTION,
    MSG_TYPE_PARENT,
    MSG_TYPE_TEACHER,
    MSG_TYPE_STAFF,
]

CHANNEL_EMAIL = "email"
CHANNEL_SMS = "sms"
CHANNEL_PUSH = "push"
CHANNEL_WHATSAPP = "whatsapp"
CHANNEL_IN_APP = "in_app"

ALL_CHANNELS = [CHANNEL_EMAIL, CHANNEL_SMS, CHANNEL_PUSH, CHANNEL_WHATSAPP, CHANNEL_IN_APP]

STATUS_DRAFT = "draft"
STATUS_SENT = "sent"
STATUS_SCHEDULED = "scheduled"
STATUS_FAILED = "failed"
STATUS_PARTIAL = "partial"

RECIPIENT_STATUS_PENDING = "pending"
RECIPIENT_STATUS_SENT = "sent"
RECIPIENT_STATUS_DELIVERED = "delivered"
RECIPIENT_STATUS_READ = "read"
RECIPIENT_STATUS_FAILED = "failed"
RECIPIENT_STATUS_BOUNCED = "bounced"

PRIORITY_NORMAL = "normal"
PRIORITY_HIGH = "high"
PRIORITY_URGENT = "urgent"

SCHEDULE_STATUS_PENDING = "pending"
SCHEDULE_STATUS_SENDING = "sending"
SCHEDULE_STATUS_COMPLETED = "completed"
SCHEDULE_STATUS_FAILED = "failed"

RECURRENCE_NONE = "none"
RECURRENCE_DAILY = "daily"
RECURRENCE_WEEKLY = "weekly"
RECURRENCE_MONTHLY = "monthly"

RECIPIENT_TYPE_USER = "user"
RECIPIENT_TYPE_STUDENT = "student"
RECIPIENT_TYPE_TEACHER = "teacher"
RECIPIENT_TYPE_PARENT = "parent"

# P15 — operational contexts a communication can be linked to. A message
# keeps ``context_type`` + ``context_id`` so it remains associated with the
# entity it was composed from (student → fee issue → contact guardian, a
# case, an admission), and templates can resolve real entity variables.
CONTEXT_STUDENT = "student"
CONTEXT_CASE = "case"
CONTEXT_FEE_DUE = "fee_due"
CONTEXT_ADMISSION = "admission"
CONTEXT_ANNOUNCEMENT = "announcement"

ALL_CONTEXTS = [
    CONTEXT_STUDENT,
    CONTEXT_CASE,
    CONTEXT_FEE_DUE,
    CONTEXT_ADMISSION,
    CONTEXT_ANNOUNCEMENT,
]
