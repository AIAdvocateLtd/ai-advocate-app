cd /app/backend
export AIA_NO_PAID=1
for f in tests/test_lex2_*.py tests/test_legal_research.py tests/test_stage2_safety.py tests/test_auth_2fa_sessions.py tests/test_global_research.py; do
  r=$(timeout 400 python -m pytest "$f" -q -p no:cacheprovider 2>&1 | tail -1); echo "$f :: $r"
done > /app/backend/evals/suites.log 2>&1
echo DONE >> /app/backend/evals/suites.log
