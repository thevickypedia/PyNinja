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

Routes
======

.. automodule:: pyninja.routes

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

.. autoclass:: pyninja.models.DiskLib(BaseModel)
   :exclude-members: _abc_impl, model_config, model_fields, model_computed_fields

====

.. autoclass:: pyninja.models.ServiceLib(BaseModel)
   :exclude-members: _abc_impl, model_config, model_fields, model_computed_fields

====

.. autoclass:: pyninja.models.ProcessorLib(BaseModel)
   :exclude-members: _abc_impl, model_config, model_fields, model_computed_fields

====

.. autoclass:: pyninja.models.WSSettings(BaseModel)
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
   :exclude-members: Payload, ServiceStatus, DiskLib, ServiceLib, ProcessorLib, WSSettings, EnvConfig, Session, RateLimit, env, database

Squire
======

.. automodule:: pyninja.squire

PyNinja - Monitor
=================

Authenticator
-------------

.. automodule:: pyninja.monitor.authenticator

Configuration
-------------

.. automodule:: pyninja.monitor.config

Routes
------

.. automodule:: pyninja.monitor.routes

Secure
------

.. automodule:: pyninja.monitor.secure

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
