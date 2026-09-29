"""Filesystem-backed records that are configuration rather than events.

The identity root lives in the Kin's SQLite database because it is revised and
audited. A persona manifest lives next to it as one small file because it is
written once by `init`, read by every later boot, and has no transactional
relationship to anything else: putting it in the database would add a migration to
describe a document.
"""
