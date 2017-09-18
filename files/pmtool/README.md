## Description

Run Project Management Tool, used for tracking various aspects of development for the OpenMRS Community.

## Running it locally

```
$ docker-compose up
```

PM tool will be available on http://localhost/

Use _CTRL + C_ to stop all containers.

To clear out stopped containers after stopping:

```
$ docker-compose down
```

## Running in production

```
$ PMTOOL_PORT=8080 docker-compose up -d
```