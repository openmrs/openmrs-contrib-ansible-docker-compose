ansible-docker-compose
=========

This in an OpenMRS ansible role responsible for deploying all the docker-compose files
required by OpenMRS infrastructure.

This is a custom role.  

## Running a docker-compose application locally

  - Install docker 1.12+ and docker-compose 1.10+
  - Move to the correct application subfolder (e.g. _files/demo_)
  - `docker-compose up` to start it, and `docker-compose down` to power it off.
  Follow more details on the README file.  

## Deploying a new docker-compose application to our infrastructure

  - Make sure all the docker images come from dockerhub
  (Use <https://hub.docker.com/u/openmrs/> for our own images).
  - Make sure every image created by you has some CI or an automated build to deploy
  a certain tag to dockerhub.
  - Create a subfolder in <https://github.com/openmrs/openmrs-contrib-ansible-docker-compose/tree/master/files>
  for your application.
  - Add docker-compose and any relevant files there.
  You should have a README file and healthchecks.
  (use docker 1.12+ and docker-compose 1.10+ to have this feature).
  The docker-compose file should work, and it should allow all credentials to
  be overridden by environment variables.
  Make sure to expose a port which is not already exposed on the docker host.
  - If you want to persist docker volumes between deployments, make sure to create a `deploy.env`
  file with the following content:

  `DESTROY_VOLUMES=false`

  By default, volumes are destroyed on every deployment.

  - Create a pull request.
