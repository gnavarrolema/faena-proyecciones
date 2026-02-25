#!/bin/bash
# Script temporal para crear WIF provider
gcloud iam workload-identity-pools providers create-oidc github-provider \
  --workload-identity-pool=github-pool \
  --location=global \
  --issuer-uri='https://token.actions.githubusercontent.com' \
  --attribute-mapping='google.subject=assertion.sub,attribute.repository=assertion.repository' \
  --attribute-condition="assertion.repository=='gnavarrolema/faena-proyecciones'" \
  --project=faena-proyecciones
