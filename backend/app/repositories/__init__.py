"""Data access only. Tenant repositories take ``workspace_id`` on every function and never commit
(the service layer owns the transaction). ``tests/test_scoping.py`` enforces the first rule.
"""
