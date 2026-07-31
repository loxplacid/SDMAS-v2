CATEGORY_STUDENT = "student_documents"
CATEGORY_STAFF = "staff_documents"
CATEGORY_CERTIFICATE = "certificates"
CATEGORY_RECEIPT = "receipts"
CATEGORY_REPORT = "reports"
CATEGORY_SCHOOL = "school_documents"

BUILTIN_CATEGORIES = [
    {
        "code": CATEGORY_STUDENT,
        "name": "Student Documents",
        "description": "Documents uploaded by or for students (transcripts, IDs, forms)",
        "allowed_roles": ["admin", "staff", "teacher"],
        "owner_type": "student",
    },
    {
        "code": CATEGORY_STAFF,
        "name": "Staff Documents",
        "description": "Documents related to staff (contracts, resumes, evaluations)",
        "allowed_roles": ["admin", "staff"],
        "owner_type": "user",
    },
    {
        "code": CATEGORY_CERTIFICATE,
        "name": "Certificates",
        "description": "Academic certificates, diplomas, and awards",
        "allowed_roles": ["admin", "staff"],
        "owner_type": "any",
    },
    {
        "code": CATEGORY_RECEIPT,
        "name": "Receipts",
        "description": "Payment receipts and financial documents",
        "allowed_roles": ["admin", "staff", "accountant"],
        "owner_type": "any",
    },
    {
        "code": CATEGORY_REPORT,
        "name": "Reports",
        "description": "Generated reports and exported data files",
        "allowed_roles": ["admin", "staff"],
        "owner_type": "any",
    },
    {
        "code": CATEGORY_SCHOOL,
        "name": "School Documents",
        "description": "General school administrative documents",
        "allowed_roles": ["admin", "staff"],
        "owner_type": "any",
    },
]

LIFECYCLE_DRAFT = "draft"
LIFECYCLE_ACTIVE = "active"
LIFECYCLE_ARCHIVED = "archived"
LIFECYCLE_DELETED = "deleted"

VALID_LIFECYCLE_TRANSITIONS = {
    LIFECYCLE_DRAFT: [LIFECYCLE_ACTIVE, LIFECYCLE_DELETED],
    LIFECYCLE_ACTIVE: [LIFECYCLE_ARCHIVED, LIFECYCLE_DELETED],
    LIFECYCLE_ARCHIVED: [LIFECYCLE_DELETED],
    LIFECYCLE_DELETED: [],
}

AUDIT_DOCUMENT_CREATE = "document.create"
AUDIT_DOCUMENT_UPDATE = "document.update"
AUDIT_DOCUMENT_DELETE = "document.delete"
AUDIT_DOCUMENT_DOWNLOAD = "document.download"
AUDIT_DOCUMENT_ARCHIVE = "document.archive"
AUDIT_DOCUMENT_SHARE = "document.share"
AUDIT_DOCUMENT_VERSION = "document.version"
