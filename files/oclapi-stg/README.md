## Description

OCL api for stg.

Check <https://github.com/OpenConceptLab/oclapi/tree/jetstream> for details.

Please set the following variables in .env:

```
ENVIRONMENT=staging
ROOT_PASSWORD=<someSecret>
AWS_ACCESS_KEY_ID=<aws_s3_creds>
AWS_SECRET_ACCESS_KEY=<write_access_aws_s3_creds>
AWS_STORAGE_BUCKET_NAME=<write_access_aws_s3_bucket_name>
OCL_API_TOKEN=<someSecret2>
SECRET_KEY=<someSecret3>
EMAIL_HOST_PASSWORD=<password_for_no_reply_at_openconceptlab_org>
BACKUP_DIR=/opt/backups
```

  - ROOT_PASSWORD, OCL_API_TOKEN, SECRET_KEY to some secret values.
  - AWS_STORAGE_BUCKET_NAME should be a bucket in AWS
  - AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are credentials for a user with write access to the bucket
  - EMAIL_HOST_PASSWORD to password for no-reply@openconceptlab.org
