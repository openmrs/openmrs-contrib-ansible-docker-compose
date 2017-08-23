## Description

OCL web for production.

Check <https://github.com/OpenConceptLab/oclweb/tree/jetstream> for details.

Please set the following variables in .env:

POSTGRES_PASSWORD to some secret value

ROOT_PASSWORD must match the value from OCL API

OCL_API_TOKEN and OCL_ANON_API_TOKEN must match the value from OCL API

OCL_API_NETWORK must match the network used by OCL API, which can be determined running `docker network ls` and by default is `directory_default`, where
`directory` is a directory with the OCL API docker-compose file.

ENVIRONMENT=staging
