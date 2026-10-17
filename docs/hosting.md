# Hosted demonstration

Arsia's hosted demo preserves the local workbench's single-process workflow.
CloudFront provides the public HTTPS hostname and forwards requests to one
Amazon Linux 2023 EC2 instance. Python 3.12 and one Uvicorn worker run under a
dedicated operating-system user. Private JSON checkpoints remain on encrypted
EBS storage; long-running generation continues outside individual HTTP requests.

The infrastructure is defined in [hosted-demo.yaml](../infra/hosted-demo.yaml).
[hosted_bootstrap.py](../scripts/hosted_bootstrap.py) installs the locked Python
dependencies, seeds an inactive fictional report and starts the systemd service.
The ZIP must contain the Python application, built `frontend/dist`, requirements
and constraints, the bootstrap script, `seed/native-config.json` and any selected
inactive `seed/runs/*.json` records. Credentials never belong in this ZIP.

## Access and credentials

The shared judge login is distributed separately by the presenter. This is a
single-workspace demonstration using fictional materials. It does not provide
per-employee authentication, separate judge accounts or enterprise SSO.

AWS Secrets Manager stores the Box application credentials, demo credentials,
exact public hostname/origin and a separate CloudFront origin token. The EC2
instance role can read only the configured artifact and secret and invoke the
configured Nova Pro inference resources. SSM provides administration without
inbound SSH. No local AWS profile or static AWS key is copied to the server.

The origin security group accepts its application port only from CloudFront's
managed origin-facing prefix list. The application also checks a separate
CloudFront secret header, explicit allowed hosts and mutation origins. CloudFront
disables caching and forwards authentication, origin headers and query strings.
The minimal anonymous `/healthz` endpoint contains no workspace information.

Browser connections use HTTPS. The CloudFront-to-EC2 origin connection currently
uses HTTP with network and header restrictions; end-to-end origin TLS is future
hardening. Shared-login access permits modifying the fictional workspace, so
credentials should be provided only to the intended reviewers.

## Operation

Set `REVIEW_DATA_DIR` to persistent private storage. The workspace configuration
is `<REVIEW_DATA_DIR>/native-config.json`; run records are stored beneath
`<REVIEW_DATA_DIR>/workbench/runs`. Keep one application process and do not use
reload mode. Before replacing code or restarting, verify every run is inactive.
The systemd service allows ongoing work time to shut down gracefully.

The current CloudFormation parameters are `ArtifactBucket`, `ArtifactKey`,
`SecretArn`, `VpcId`, `SubnetId`, `ImageId` and `CloudFrontPrefixListId`. Resolve
the current regional AMI and CloudFront prefix list before deployment. Once the
distribution allocates its hostname, set `ARSIA_PUBLIC_ORIGIN` and
`ARSIA_ALLOWED_HOSTS` in the secret; bootstrap waits for this binding.

EC2, EBS, public IPv4 and applicable CloudFront/Bedrock usage continue to incur
charges while resources remain. After judging, the owner should explicitly
decide whether to retain or remove the deployment. The root EBS volume is retained
on instance deletion so checkpoint disposal remains an explicit decision.
