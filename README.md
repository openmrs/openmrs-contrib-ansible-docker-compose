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
  
### Process   
  - Create a branch/fork of this repository. 
  - Create a subfolder in <https://github.com/openmrs/openmrs-contrib-ansible-docker-compose/tree/master/files>
  for your application. All files required by your application, including `docker-compose.yaml` file will live there. 
  - Create a pull request and notify the infrastructure team (telegram or talk). 
  Let us know which DNS name you'd like to use. 
  Let us know if you prefer to have newer images deployed automatically from a Bamboo build or when pushed to dockerhub. 
  - Infrastructure team will merge the pull request, add passwords and secrets, configure 
  deployment of newer versions of the image, and deploy this docker-compose app to a server.
  
_Note: while you are can deploy new versions of the application without infrastructure team involvement, 
  changes to docker-compose files will need to be deployed by us._
 
### Guidelines 
 Your docker-compose file needs to follow the following rules:
  
  - All the docker images should come from dockerhub
  (Use <https://hub.docker.com/u/openmrs/> for our own images).
  You cannot build an image from this repository. 
  - Docker images should have CI or an automated build to deploy to dockerhub.
  - Pay a lot of attention your image tags. As soon as an image is pushed to dockerhub, 
  deployment will be automatically started. So it's recommended to have an image tag per server 
  deployed (e.g. 'stg' and 'prd', instead of using 'latest'). 
  - Docker images should _never_ contain passwords and secrets hardcoded. 
  Always allow secrets to be overridden by environment variables. 
  - Add a README file. 
  - Add healthchecks to all docker containers. 
  (use docker 1.12+ and docker-compose 1.10+ to have this feature).
  - Add a 'restart: always' to your docker containers, otherwise
  they won't be started when the host is restarted. 
  - Expose the port which should be called from the web interface.
  - If you want to persist docker volumes between deployments, make sure to create a `deploy.env`
  file with the following content:

  `DESTROY_VOLUMES=false`

  By default, volumes are destroyed on every deployment.
