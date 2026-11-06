import os

# Automated tests deliberately simulate failures; keep them out of Sentry alerting.
os.environ["SENTRY_DSN"] = ""
