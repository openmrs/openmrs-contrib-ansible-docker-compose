## Description

Run OpenHIM for use by the [Open Concept Lab](https://openconceptlab.org/).

The docker images are generated and maintained by [Jembi](https://jembi.org/).

## Running it locally

```
$ docker-compose up
```

OpenHIM console will be available on http://localhost/

Use _CTRL + C_ to stop all containers.

To clear out stopped containers after stopping:

```
$ docker-compose down
```

To free up all resources (including daa volume) after stopping:

```
$ docker-compose down -v
```

## Initial setup

The first time OpenHIM is run, authenticate using these credentials:

* E-mail address: **root**<span>**@**</span>**openmrs.org**
* Password: **openhim-password**

On first successful login, you should be prompted to reset the root password. Use a tool like [LastPass](https://www.lastpass.com/) or site like [passwordgenerator.net](https://passwordsgenerator.net/) to generate a secure password at least 20 characters long for the root password.