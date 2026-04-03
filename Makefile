dev-web:
	@trap 'kill 0' INT TERM EXIT; \
	cd backend && AUTH_ENABLED=true AUTH_MODE=dev FRONTEND_APP_URL=http://127.0.0.1:3001 . .venv/bin/activate && python -m app.db.migrate && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 & \
	cd web && NEXT_PUBLIC_DEV_MODE=true NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 npm run dev -- --port 3001 & \
	wait
