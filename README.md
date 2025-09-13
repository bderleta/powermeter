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
- Run as a daemon:
```sh
docker compose up -d
```

## Running without container

```sh
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python ./main.py --config=<config-filename>
```

## Configuration

### `[modbus]` section

See [pymodbus docs](https://pymodbus.readthedocs.io/en/latest/source/client.html#pymodbus.client.ModbusSerialClient).
Supported options:
- `framer`
- `timeout`
- `baudrate`
- `bytesize`
- `parity`
- `stopbits`
- [`logging`](https://pymodbus.readthedocs.io/en/latest/source/library/pymodbus.html#pymodbus.pymodbus_apply_logging_config)

### `[server]` section

Supported options:
- `port` - HTTP port for listening to incoming requests

### `[meters]` section

Accepts entries in format `<device_id>=<type>`. Supported types:
- `taiyedq`
- `finder`
- `eastron` 

## Supported meters

This service has been tested with following devices:
- [Eastron SDM120M Modbus](https://www.eastroneurope.com/products/view/sdm120modbus)
- [Finder 7M.24.8.230.0210](https://www.findernet.com/en/worldwide/series/7m-series-smart-energy-meters/type/type-7m-24-single-phase-bi-directional-energy-meters-with-backlit-lcd-display/)
- [Taiye TAC1100/TAC2100](http://www.taiye-electric.com/productdetail/tac2100-single-phase-din-rail-energy-meter.html)


## Supported RS485 adapters

This service has been tested only with [Waveshare 17286](https://www.waveshare.com/usb-to-rs485.htm).
