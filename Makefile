dev-web:
	@trap 'kill 0' INT TERM EXIT; \
	cd backend && . .venv/bin/activate && python -m app.db.migrate && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 & \
	cd web && pnpm run dev -- --port 3001 & \
	wait

seed-enterprise-acl:
	cd backend && . .venv/bin/activate && python -m app.seed.enterprise_acl
