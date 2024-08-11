.. PyNinja documentation master file, created by
   sphinx-quickstart on Sat Aug 10 21:49:31 2024.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to PyNinja's documentation!
===================================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   README

PyNinja - Main
==============

.. automodule:: pyninja.main

Authenticator
=============
.. automodule:: pyninja.auth

Routers
=======

.. automodule:: pyninja.routers

Monitors
========

Docker
------

.. automodule:: pyninja.dockerized

Process
-------

.. automodule:: pyninja.process

Service
-------

.. automodule:: pyninja.service

Database
========

.. automodule:: pyninja.database

RateLimiter
===========

.. automodule:: pyninja.rate_limit

Exceptions
==========

.. automodule:: pyninja.exceptions

Models
======

.. autoclass:: pyninja.models.Payload(BaseModel)
   :exclude-members: _abc_impl, model_config, model_fields, model_computed_fields

====

.. autoclass:: pyninja.models.ServiceStatus(BaseModel)
   :exclude-members: _abc_impl, model_config, model_fields, model_computed_fields

====

.. autoclass:: pyninja.models.Session(BaseModel)
   :exclude-members: _abc_impl, model_config, model_fields, model_computed_fields

====

.. autoclass:: pyninja.models.RateLimit(BaseModel)
   :exclude-members: _abc_impl, model_config, model_fields, model_computed_fields

====

.. autoclass:: pyninja.models.EnvConfig(BaseModel)
   :exclude-members: _abc_impl, model_config, model_fields, model_computed_fields

====

.. automodule:: pyninja.models
   :exclude-members: Payload, ServiceStatus, EnvConfig, Session, RateLimit, env, database

Squire
======

.. automodule:: pyninja.squire

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
