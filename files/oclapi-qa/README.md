## Description

OCL api for qa.

Check <https://github.com/OpenConceptLab/oclapi/tree/jetstream> for details.

Please set the following variables in .env:

```
ENVIRONMENT=qa
ROOT_PASSWORD=<someSecret>
NEW_RELIC_API_KEY=
AWS_ACCESS_KEY_ID=<aws_s3_creds>
AWS_SECRET_ACCESS_KEY=<write_access_aws_s3_creds>
AWS_STORAGE_BUCKET_NAME=<write_access_aws_s3_bucket_name>
OCL_API_TOKEN=<someSecret2>
```

  - ROOT_PASSWORD and OCL_API_TOKEN to some secret values.
  - AWS_STORAGE_BUCKET_NAME should be a bucket in AWS
  - AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are credentials for a user with write access to the bucket
  - NEW_RELIC_API_KEY should be left blank for now
