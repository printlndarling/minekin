# Test-only oracle

This directory belongs to the offline test/asserter side. Product packages,
runtime inputs, Bridge messages, projections, and model-facing data must never
read or import its contents. Dependency and canary tests enforce that boundary.
