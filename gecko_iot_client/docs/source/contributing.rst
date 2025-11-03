Contributing
============

Thank you for your interest in contributing to the Gecko IoT Client! This document provides guidelines for contributing to the project.

Code of Conduct
---------------

Be respectful and inclusive in all interactions. We welcome contributions from developers of all backgrounds and experience levels.

Getting Started
---------------

1. **Fork the repository** on GitHub
2. **Clone your fork** locally
3. **Create a feature branch** from main
4. **Make your changes** with tests
5. **Submit a pull request**

Development Environment
----------------------

Set up your development environment:

.. code-block:: bash

   # Clone your fork
   git clone https://github.com/your-username/geckoIotClient.git
   cd geckoIotClient/python/gecko_iot_client
   
   # Create virtual environment
   python -m venv venv
   source venv/bin/activate
   
   # Install development dependencies
   pip install -e .[dev,docs]

Types of Contributions
---------------------

We welcome several types of contributions:

Bug Reports
~~~~~~~~~~~

When reporting bugs:

* Use the GitHub issue template
* Include Python version and OS
* Provide minimal reproduction example
* Include error messages and stack traces

Feature Requests
~~~~~~~~~~~~~~~~

For new features:

* Check if it already exists
* Explain the use case
* Provide implementation ideas
* Consider backwards compatibility

Code Contributions
~~~~~~~~~~~~~~~~~

All code contributions should:

* Include tests
* Follow code style guidelines
* Update documentation
* Pass all existing tests

Documentation
~~~~~~~~~~~~

Documentation improvements:

* Fix typos and grammar
* Add examples and clarifications
* Update outdated information
* Improve API documentation

Pull Request Process
-------------------

1. **Create Feature Branch**

.. code-block:: bash

   git checkout -b feature/your-feature-name

2. **Make Changes**

* Write clear, concise code
* Add tests for new functionality
* Update documentation as needed

3. **Test Your Changes**

.. code-block:: bash

   # Run tests
   pytest
   
   # Check code style
   black src/ tests/
   isort src/ tests/
   flake8 src/ tests/
   
   # Build docs
   cd docs && make html

4. **Commit Changes**

Use clear commit messages:

.. code-block:: bash

   git add .
   git commit -m "Add: New zone type for water features
   
   - Implement WaterFeatureZone class
   - Add validation for water flow rates
   - Include tests and documentation"

5. **Push and Create PR**

.. code-block:: bash

   git push origin feature/your-feature-name

Then create a pull request on GitHub.

Code Style Guidelines
--------------------

Python Style
~~~~~~~~~~~~

Follow PEP 8 with these specifics:

* **Line length**: 88 characters (Black default)
* **Imports**: Use isort for import organization
* **Type hints**: Include type hints for all public methods
* **Docstrings**: Use Google-style docstrings

Example:

.. code-block:: python

   from typing import Optional, Dict, Any
   
   
   class ExampleZone(AbstractZone):
       """
       Example zone for demonstration purposes.
       
       This zone shows proper code style including type hints,
       docstrings, and validation.
       
       Args:
           id: Unique zone identifier
           name: Optional zone name
           zone_type: Type of zone
       """
       
       def set_value(self, value: float, active: Optional[bool] = None) -> None:
           """
           Set a value for this zone.
           
           Args:
               value: The value to set (0.0 to 100.0)
               active: Whether to activate the zone
               
           Raises:
               ValueError: If value is outside valid range
               
           Example:
               >>> zone.set_value(75.0, active=True)
           """
           if not 0.0 <= value <= 100.0:
               raise ValueError(f"Value must be 0-100, got {value}")
           
           # Implementation here

Documentation Style
~~~~~~~~~~~~~~~~~~

* Use reStructuredText (RST) format
* Include code examples
* Keep examples practical and realistic
* Update both docstrings and user guides

Testing Guidelines
-----------------

Test Requirements
~~~~~~~~~~~~~~~~

* **Unit tests** for all new code
* **Integration tests** for transport layers
* **Validation tests** for zone models
* **Example tests** to ensure examples work

Test Structure
~~~~~~~~~~~~~

.. code-block:: python

   class TestNewFeature:
       """Test suite for new feature"""
       
       def test_basic_functionality(self):
           """Test basic feature operation"""
           # Arrange
           zone = create_test_zone()
           
           # Act
           result = zone.perform_action()
           
           # Assert
           assert result is not None
           assert zone.state == "expected"
       
       def test_edge_cases(self):
           """Test edge cases and error conditions"""
           with pytest.raises(ValueError):
               zone.invalid_operation()
       
       @pytest.mark.integration
       def test_with_real_transport(self):
           """Integration test with real transport"""
           # Only run if credentials available
           pass

Mock Guidelines
~~~~~~~~~~~~~~

Use mocks for external dependencies:

.. code-block:: python

   from unittest.mock import Mock, patch
   
   
   def test_with_mock_transport():
       """Test using mock transport"""
       mock_transport = Mock()
       mock_transport.publish_desired_state.return_value = Future()
       
       zone = FlowZone(id="test", zone_type=ZoneType.FLOW_ZONE)
       zone.set_state_manager(Mock())
       
       # Test without real network calls

Documentation Guidelines
-----------------------

API Documentation
~~~~~~~~~~~~~~~~

* Document all public methods and classes
* Include parameter types and descriptions
* Provide usage examples
* Document exceptions

User Documentation
~~~~~~~~~~~~~~~~~

* Write for different skill levels
* Include complete working examples
* Show real-world use cases
* Keep examples up-to-date

Code Examples
~~~~~~~~~~~~

All examples should:

* Be complete and runnable
* Use realistic parameters
* Include error handling
* Follow code style guidelines

Release Process
--------------

Version Numbering
~~~~~~~~~~~~~~~~

We use semantic versioning (semver):

* **Major** (1.0.0): Breaking changes
* **Minor** (0.1.0): New features, backwards compatible
* **Patch** (0.0.1): Bug fixes

Release Checklist
~~~~~~~~~~~~~~~~

Before releasing:

* [ ] All tests pass
* [ ] Documentation updated
* [ ] Version number updated
* [ ] Changelog updated
* [ ] Tag created

Review Process
-------------

All contributions go through review:

1. **Automated checks** must pass
2. **Code review** by maintainer
3. **Discussion** of implementation
4. **Approval** and merge

Review Criteria
~~~~~~~~~~~~~~

* Code quality and style
* Test coverage
* Documentation completeness
* Backwards compatibility
* Performance impact

Community
---------

Getting Help
~~~~~~~~~~~~

* **GitHub Discussions**: General questions
* **GitHub Issues**: Bug reports and feature requests
* **Documentation**: Check existing docs first

Communication
~~~~~~~~~~~~

* Be respectful and constructive
* Ask questions if unclear
* Provide context in discussions
* Help others when possible

Recognition
~~~~~~~~~~

Contributors are recognized:

* In changelog entries
* In documentation credits
* In release notes

Issue Guidelines
---------------

Bug Reports
~~~~~~~~~~

Include:

* Python version and OS
* Gecko IoT Client version
* Minimal reproduction example
* Full error message and traceback
* Expected vs actual behavior

.. code-block:: python

   # Bug reproduction example
   from gecko_iot_client import GeckoIotClient
   
   # This should work but raises an error
   client = GeckoIotClient("test", None)
   zones = client.get_zones()  # Error occurs here

Feature Requests
~~~~~~~~~~~~~~~

Include:

* Use case description
* Proposed API (if applicable)
* Alternative solutions considered
* Implementation complexity estimate

Security Issues
~~~~~~~~~~~~~~

For security vulnerabilities:

* **Do not** create public issues
* Email maintainers directly
* Include full details privately
* Allow time for fix before disclosure

Thank You
---------

Thank you for contributing to the Gecko IoT Client! Your contributions help make IoT device control more accessible and reliable for everyone.