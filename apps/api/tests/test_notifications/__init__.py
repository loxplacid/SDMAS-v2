# Ensure all models are imported so Base.metadata knows about every table.
# The DeviceToken model has a FK to users.id, so the User model must be
# registered before Base.metadata.create_all() can resolve it.
from app.domains.auth.models import User  # noqa: F401
