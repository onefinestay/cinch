from flask import session
from flask.ext.admin.contrib.sqla import ModelView

from cinch import admin, app, db
from cinch.auth.decorators import is_authenticated
from cinch.models import Project
from cinch.jenkins.models import Job


class AdminView(ModelView):
    def is_accessible(self):
        admin_users_str = app.config.get('ADMIN_USERS', '')
        admin_users = admin_users_str.split(',')

        if not admin_users:
            return is_authenticated()

        return is_authenticated() and session['gh-username'] in admin_users


for model in Project, Job:
    view = AdminView(model, db.session)
    admin.add_view(view)
