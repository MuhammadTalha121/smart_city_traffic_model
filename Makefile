.PHONY: load-test test

load-test:
	@echo "Running load test..."
	@chmod +x scripts/run_load_test.sh
	@./scripts/run_load_test.sh

test:
	py -m pytest tests/ -v