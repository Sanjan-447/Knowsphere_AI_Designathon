"""
Custom Flask CLI commands.

Usage:
    flask seed-roles          # idempotently create Admin/Manager/Employee roles
    flask seed-admin          # create (or reset) the bootstrap admin user
"""
import click

from app.extensions import db
from app.rbac.models import Role, ensure_default_roles, ROLE_ADMIN
from app.auth.models import User


def register_cli(app):
    @app.cli.command("seed-roles")
    def seed_roles():
        """Create the default Admin/Manager/Employee roles if they don't exist."""
        ensure_default_roles()
        click.echo("Default roles ensured: admin, manager, employee.")

    @app.cli.command("seed-admin")
    @click.option("--email", prompt=True)
    @click.option("--display-name", prompt="Display name")
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
    def seed_admin(email, display_name, password):
        """Create the first Admin user. Safe to re-run — updates the password if the user exists."""
        ensure_default_roles()
        admin_role = Role.query.filter_by(name=ROLE_ADMIN).first()

        email = email.strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            user.set_password(password)
            user.display_name = display_name
            user.role_id = admin_role.id
            user.is_active = True
            db.session.commit()
            click.echo(f"Existing user '{email}' updated to Admin with new password.")
        else:
            user = User(email=email, display_name=display_name, role_id=admin_role.id)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            click.echo(f"Admin user '{email}' created.")
