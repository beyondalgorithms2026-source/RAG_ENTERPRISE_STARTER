dev-web:
	@trap 'kill 0' INT TERM EXIT; \
	cd backend && . .venv/bin/activate && python -m app.db.migrate && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 & \
	cd web && pnpm run dev -- --port 3001 & \
	wait

seed-enterprise-acl:
	cd backend && . .venv/bin/activate && python -m app.seed.enterprise_acl

scenario-validate:
	cd backend && . .venv/bin/activate && python -m unittest tests.test_admin_modules_m29 tests.test_scenario_build_packs_m30 tests.test_access_strategy_m28 tests.test_security_posture_m23_m24

repo-hygiene-check:
	@if git ls-files --error-unmatch web/.env.local >/dev/null 2>&1; then echo "web/.env.local is still tracked"; exit 1; fi
	@if git ls-files --error-unmatch web/tsconfig.tsbuildinfo >/dev/null 2>&1; then echo "web/tsconfig.tsbuildinfo is still tracked"; exit 1; fi
	@if git ls-files --error-unmatch eval_report_retrieval.json >/dev/null 2>&1; then echo "eval_report_retrieval.json is still tracked"; exit 1; fi
	@echo "Repo hygiene checks passed."

reader-clarity-check:
	cd backend && . .venv/bin/activate && python -m unittest tests.test_reader_clarity_m32 tests.test_repo_hygiene_m31 tests.test_m27_reuse_blueprint_docs tests.test_scenario_build_packs_m30
