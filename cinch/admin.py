from flask.ext.admin.contrib.sqla import ModelView

from cinch import admin, db
from cinch.auth.decorators import is_authenticated
from cinch.models import Project
from cinch.jenkins.models import Job


class AdminView(ModelView):
    def is_accessible(self):
        return is_authenticated()


for model in Project, Job:
    view = AdminView(model, db.session)
    admin.add_view(view)
