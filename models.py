from flask_login import UserMixin


class User(UserMixin):
    """Thin wrapper around a users row for Flask-Login. Role is carried
    through for future RBAC enforcement but nothing reads it yet."""

    def __init__(self, row):
        self.id = str(row["id"])
        self.username = row["username"]
        self.role = row["role"]
        self.password_hash = row["password_hash"]

    @property
    def actor(self):
        """The identity string written into case_events.actor — matches
        the 'staff:jdoe' convention documented in schema.sql."""
        return f"{self.role}:{self.username}"
