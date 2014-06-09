# Required for authenticating users with github.
# see https://github-flask.readthedocs.org/en/latest/
export CINCH_GITHUB_CLIENT_ID=
export CINCH_GITHUB_CLIENT_SECRET=
export CINCH_GITHUB_CALLBACK_URL=

# The token for the application to authenticate with when making
# requests to the github api
export CINCH_GITHUB_TOKEN=

# The secret key required for flask session management.
# see http://flask.pocoo.org/docs/quickstart/#sessions
export CINCH_SECRET_KEY=


## optional configuration

# For configuring a sentry instance to handle exception logging
export CINCH_SENTRY_DSN=

# A sqlalchemy parseable database identifier
export CINCH_DB_URI=

# URL to jenkins instance (for links to builds)
export CINCH_JENKINS_URL=
