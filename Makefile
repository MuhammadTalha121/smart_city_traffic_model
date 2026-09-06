.PHONY: load-test test validate-standards

load-test:
	@echo "Running load test..."
	@chmod +x scripts/run_load_test.sh
	@./scripts/run_load_test.sh

test:
	py -m pytest tests/ -v

validate-standards:
	py -m pytest tests/test_standards_compliance.py -v