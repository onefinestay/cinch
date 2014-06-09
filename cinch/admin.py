import logging

from flask import session
from flask.ext.admin.contrib.sqla import ModelView

from cinch import admin, app, db
from cinch.auth.decorators import is_authenticated
from cinch.models import Project
from cinch.jenkins.models import Job

log = logging.getLogger(__name__)


class AdminView(ModelView):
    def is_accessible(self):
        admin_users_str = app.config.get('ADMIN_USERS', '')
        admin_users = admin_users_str.split(',')

        if not admin_users:
            log.warn(
                'No admin users configured. Assign a comma-separated list of '
                'github usernames ADMIN_USERS in order to list which users '
                'should have access to admin screens')
            return False

        return is_authenticated() and session['gh-username'] in admin_users


for model in Project, Job:
    view = AdminView(model, db.session)
    admin.add_view(view)
