# Auth security prep (2026-11-19, PREVIEW — not deployed except Google hotfix)
## Deployed hotfix (owner-approved): Google email-only sign-in removed; access tokens audience-checked; social logins honour 2FA; Apple button hidden (APPLE_WEB_SIGNIN_ENABLED!="1").
## Apple: Services ID app.aiadvocate.signin exists; Apple returns "Invalid web redirect url" for https://aiadvocate.co.uk/ -> return URL/domain not registered.
## Preview-only (needs approval + TOTP_ENC_KEY secret in prod before deploy):
- account_security.py: email codes (HMAC hash, 5 min, single use, 30s/5h resend limits, 5 tries/code, 10 wrong/15min per account), Fernet-encrypted TOTP secrets (enc: prefix; legacy plaintext still read), token_version (tv claim; tokens without tv valid while version 0), session_valid rejects pre_2fa tmp tokens, admin email-code exclusion, MFA_BREAKGLASS_USER_ID env.
- server.py endpoints: /auth/security/status, /auth/security/reauth-code, /auth/2fa/setup (fresh auth), /verify (revokes other sessions, returns new token), /disable, /recovery-codes, /email/enable|disable|resend, /2fa/login (email|totp|recovery, TOTP single-use step), /auth/sessions/revoke, /admin/users/reset-2fa, /admin/security/admin-totp-required (needs own TOTP + code). reset-password revokes sessions + 2FA challenge. Admin gate in require_admin/_check_admin_user/_check_founder_only when app_settings security.admin_totp_required.
- Frontend: components/SecuritySettingsCard.jsx in Settings; twofa screen method-aware + resend.
- Tests: tests/test_auth_2fa_sessions.py 11/11; iteration_58 frontend 100%.
