"""AWS Lambda entrypoint for the FastAPI app.

Serves the whole application (REST API + Inngest ``/api/inngest``) behind a
Lambda Function URL via Mangum. Secrets are resolved from AWS Secrets Manager
at cold start (see ``api.lambda_runtime``).
"""

from __future__ import annotations

from mangum import Mangum

from api.app import create_app
from api.lambda_runtime import hydrate_env_from_secrets

hydrate_env_from_secrets()

app = create_app()
handler = Mangum(app, lifespan="off")
