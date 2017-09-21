## Description

Run OpenHIM for use by the [Open Concept Lab](https://openconceptlab.org/).

The docker images are generated and maintained by [Jembi](https://jembi.org/).

## Running it locally

```
$ docker-compose up -d
```

OpenHIM console will be available on http://localhost/

To clear out stopped containers after stopping:

```
$ docker-compose down
```

To free up all resources (including daa volume) after stopping:

```
$ docker-compose down -v
```

## Running it in production

```
$ docker-compose up -d
```

Ports can be set as needed on the production server via environmental variables:

* `OPENHIM_CONSOLE_PORT` (default 80): web application. Expose publically via proxy HTTPS with LetsEncrypt.
* `OPENHIM_API_PORT` (default 8080): API calls to OpenHIM. If changed, then the `port` setting in the `openhim-console-config.json` file should be updated to specify this same port.
* `OPENHIM_HTTPS_PORT` (default 5000): Direct, secure calls to OpenHIM go to this port. Can be exposed publically.
* `OPENHIM_HTTP_PORT` (deafult 5001): Direct, insecure calls to OpenHIM go to this port. We do not plan to use or expose this insecure port, so this setting is currently ignored.

## Initial setup

The first time OpenHIM is run, authenticate using these credentials:

* E-mail address: **root**<span>**@**</span>**openmrs.org**
* Password: **openhim-password**

On first successful login, you should be prompted to reset the root password. Use a tool like [LastPass](https://www.lastpass.com/) or site like [passwordgenerator.net](https://passwordsgenerator.net/) to generate a secure password at least 20 characters long for the root password.