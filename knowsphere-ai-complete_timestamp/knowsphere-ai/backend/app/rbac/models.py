"""
RBAC foundation for Phase 1.

Phase 1 ships a simple, fixed three-role model (Admin / Manager / Employee)
stored as a lookup table rather than freeform strings, so it can grow into
the full Role/Permission/ResourcePolicy model from the architecture blueprint
without a breaking migration later — the `roles` table and `User.role_id`
foreign key are already the right shape for that.
"""
from app.extensions import db

# Canonical role names. Kept as constants (not a Python Enum bound to the
# column) so seeding/display logic can iterate over them easily.
ROLE_ADMIN = "admin"
ROLE_MANAGER = "manager"
ROLE_EMPLOYEE = "employee"

DEFAULT_ROLES = [
    (ROLE_ADMIN, "Full administrative access, including user and provider management."),
    (ROLE_MANAGER, "Elevated access for team leads; scoped administrative capabilities in later phases."),
    (ROLE_EMPLOYEE, "Standard end-user access."),
]


class Role(db.Model):
    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())

    users = db.relationship("User", back_populates="role")

    def to_dict(self):
        return {"id": self.id, "name": self.name, "description": self.description}

    def __repr__(self):
        return f"<Role {self.name}>"


def ensure_default_roles():
    """Idempotently create the default roles. Safe to call on every app startup."""
    for name, description in DEFAULT_ROLES:
        if not Role.query.filter_by(name=name).first():
            db.session.add(Role(name=name, description=description))
    db.session.commit()
