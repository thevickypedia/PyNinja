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

Exceptions
==========

.. automodule:: pyninja.exceptions

Routers
=======

.. automodule:: pyninja.routers

Monitors
========

Process
-------

.. automodule:: pyninja.process

Service
-------

.. automodule:: pyninja.service

Squire
======

.. autoclass:: pyninja.squire.Payload(BaseModel)
   :exclude-members: _abc_impl, model_config, model_fields, model_computed_fields

====

.. autoclass:: pyninja.squire.ServiceStatus(BaseModel)
   :exclude-members: _abc_impl, model_config, model_fields, model_computed_fields

====

.. autoclass:: pyninja.squire.EnvConfig(BaseModel)
   :exclude-members: _abc_impl, model_config, model_fields, model_computed_fields

====

.. automodule:: pyninja.squire
   :exclude-members: Payload, ServiceStatus, EnvConfig

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
