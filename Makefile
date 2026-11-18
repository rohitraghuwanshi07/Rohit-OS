.PHONY: demo mutation report deps test engine-test kernel-test kernel-shell ui serve all
all: test
deps:
	python3 -m pip install -U -r requirements.txt
test: engine-test kernel-test
demo: serve
mutation:
	python3 tools/mutation_check.py
report:
	python3 tools/build_report.py
engine-test:
	python3 -m pytest os-engine/tests -q
kernel-test:
	$(MAKE) -C kernel test
kernel-shell:
	$(MAKE) -C kernel shell-test
ui:
	cd frontend && npm install && npm run build
serve: ui
	cd backend && python3 -m uvicorn app:app --port 8000   # open http://127.0.0.1:8000
