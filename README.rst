CInch - Making CI a cinch
=========================

`Cinch <https://github.com/onefinestay/cinch>`_ is a continuous
integration tool designed to report the releasable status of
individual branches (pull requests) on public or private GitHub
projects.

.. note:: This project is very much a work in progress while we
          develop our release process towards Continuous Integration
          and Delivery.

Cinch is built to support configuring different success criteria for
different projects from a number of different sources (eg.
`GitHub <https://github.com/>`_, `Jenkins <http://jenkins-ci.org/>`_,
and `Travis <https://travis-ci.org/>`_ with a modular pattern to
support extending to include new or custom tools).


Getting started
---------------

Cinch is a `Flask <http://flask.pocoo.org/>`_ web application. To
install it's dependencies, run the following from within a new
`virutalenv <https://pypi.python.org/pypi/virtualenv/>`_::

    $ pip install -r requirements.txt

There's an example set of environment variables that will need to be
configured in order for cinch to run. To get up and running you can
copy this file and fill in the details for your local environment.

From within the cinch project directory::

    $ cp setup_env.sample.sh setup_env.sh
    $ vim setup_env.sh  # Fill in each setting according to the instructions
    $ source setup_env.sh

.. note:: Any environment variables prefixed with ``CINCH_`` will
          have the prefix stripped and will be added to the app
          configuration for access by plugins.


Then to run the application::

    $ python runserver.py

