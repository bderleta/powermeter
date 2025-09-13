# Powermeter

Reads some data from power meters. Currently supported are Eastron SDM120M, Taiye TAC1100 and Finder 7M.24.
It binds HTTP server on specified port and serves data in Prometheus metrics format on `/metrics` endpoint.
No support or warranty of any kind is provided for this project and no feature requests will be accepted.

## Building container

```sh
docker build -t powermeter .
```

## Running container

- Prepare .conf file (sample .conf files are included). Configure your meters, Modbus transmission settings and serial device.
- Prepare compose.yml file for Docker Compose (you can take a look at one of included ones). Map your serial device for container to use.
- Run ```sh
docker compose up -d
```
