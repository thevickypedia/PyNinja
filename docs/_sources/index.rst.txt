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

====

.. automodule:: pyninja.startup

PyNinja - Executors
===================

API Authenticator
-----------------
.. automodule:: pyninja.executors.auth

Database
--------
.. automodule:: pyninja.executors.database

Multifactor Authentication
--------------------------
.. automodule:: pyninja.executors.multifactor

API Routes
----------
.. automodule:: pyninja.routes.fullaccess

====

.. automodule:: pyninja.routes.ipaddr

====

.. automodule:: pyninja.routes.metrics

====

.. automodule:: pyninja.routes.namespace

====

.. automodule:: pyninja.routes.orchestration

====

.. automodule:: pyninja.executors.routers

Squire
------
.. automodule:: pyninja.executors.squire

API Routes - Certificates
=========================

Certificates
------------
.. automodule:: pyninja.routes.certificates

API Routes - Large Scale
========================

Download
--------
.. automodule:: pyninja.routes.download

====

Upload
------
.. automodule:: pyninja.routes.upload


PyNinja - Features
==================

Application
-----------
.. automodule:: pyninja.features.application

Certificates
------------
.. automodule:: pyninja.features.certificates

Docker
------
.. automodule:: pyninja.features.dockerized

Operations
----------
.. automodule:: pyninja.features.operations

Process
-------
.. automodule:: pyninja.features.process

Service
-------
.. automodule:: pyninja.features.service

Zipper
------
.. automodule:: pyninja.features.zipper

PyNinja - Modules
=================
Cache
-----
.. automodule:: pyninja.modules.cache

Enums
-----
.. automodule:: pyninja.modules.enums
   :exclude-members: StrEnum

Exceptions
----------
.. automodule:: pyninja.modules.exceptions

Models
------

.. autoclass:: pyninja.modules.models.RoutingHandler(BaseModel)
   :exclude-members: _abc_impl, model_config, model_fields, model_computed_fields

====

.. autoclass:: pyninja.modules.models.ServiceStatus(BaseModel)
   :exclude-members: _abc_impl, model_config, model_fields, model_computed_fields

====

.. autoclass:: pyninja.modules.models.Architecture(BaseModel)
   :exclude-members: _abc_impl, model_config, model_fields, model_computed_fields

====

.. autoclass:: pyninja.modules.models.Session(BaseModel)
   :exclude-members: _abc_impl, model_config, model_fields, model_computed_fields

====

.. autoclass:: pyninja.modules.models.WSSession(BaseModel)
   :exclude-members: _abc_impl, model_config, model_fields, model_computed_fields

====

.. autoclass:: pyninja.modules.models.RateLimit(BaseModel)
   :exclude-members: _abc_impl, model_config, model_fields, model_computed_fields

====

.. autoclass:: pyninja.modules.models.FileIO(BaseModel)
   :exclude-members: _abc_impl, model_config, model_fields, model_computed_fields

====

.. autoclass:: pyninja.modules.models.EnvConfig(BaseModel)
   :exclude-members: _abc_impl, model_config, model_fields, model_computed_fields

====

.. automodule:: pyninja.modules.models
   :exclude-members: RoutingHandler, ServiceStatus, Architecture, Session, WSSession, RateLimit, FileIO, EnvConfig, session, ws_session, env, database, architecture

Payloads
--------
.. autoclass:: pyninja.modules.payloads.RunCommand(BaseModel)
   :exclude-members: _abc_impl, model_config, model_fields, model_computed_fields

====

.. autoclass:: pyninja.modules.payloads.ListFiles(BaseModel)
   :exclude-members: _abc_impl, model_config, model_fields, model_computed_fields

====

.. autoclass:: pyninja.modules.payloads.GetFile(BaseModel)
   :exclude-members: _abc_impl, model_config, model_fields, model_computed_fields

RateLimit
---------
.. automodule:: pyninja.modules.rate_limit

Secure
---------
.. automodule:: pyninja.modules.secure

Tree - Directory Structure
--------------------------
.. automodule:: pyninja.modules.tree

PyNinja - Monitor
=================

Authenticator
-------------
.. automodule:: pyninja.monitor.authenticator

Configuration
-------------
.. automodule:: pyninja.monitor.config

Drive
-----
.. automodule:: pyninja.monitor.drive

Resources
---------
.. automodule:: pyninja.monitor.resources

Routes
------
.. automodule:: pyninja.monitor.routes

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
