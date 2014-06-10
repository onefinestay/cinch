noop:
	@true

test:
	PYTHONPATH=. py.test --tb=short
