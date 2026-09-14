#!/bin/bash
# A script to run the frontend server independently and then the playwright tests against it
cd app/frontend
PORT=3100 HOSTNAME=127.0.0.1 NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_Y2xlcmsuZXhhbXBsZS5jb20k CLERK_SECRET_KEY=sk_test_mock FLASK_API_PROXY_SECRET=test-proxy-secret node .next/standalone/server.js &
SERVER_PID=$!
sleep 5
echo "Server started with PID: $SERVER_PID"
PLAYWRIGHT_BASE_URL=http://127.0.0.1:3100 NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_Y2xlcmsuZXhhbXBsZS5jb20k npx playwright test
kill $SERVER_PID
