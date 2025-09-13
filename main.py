#!/usr/bin/env python

import os
import math
import struct
import time
import configparser
import http.server
import socketserver
import argparse
import logging

import pymodbus.client as ModbusClient
from pymodbus import (
    FramerType,
    ModbusException,
    pymodbus_apply_logging_config,
)

parser = argparse.ArgumentParser(
	prog='Powermeter',
	description='Modbus power meter metric reader/server for Prometheus'
)
parser.add_argument('--config', dest='config', type=str, help='Configuration file path', default='/etc/opt/powermeter.conf')
args = parser.parse_args()
fallback_config = os.path.abspath(os.path.dirname(__file__)) + "/powermeter.conf"
if args.config and os.path.isfile(args.config):
	config_path = args.config
elif os.path.isfile(fallback_config):
	config_path = fallback_config
else:
	raise FileNotFoundError

config = configparser.ConfigParser()
config.read(config_path)

modbus_logging=config.get("modbus", "logging")
if modbus_logging:
	pymodbus_apply_logging_config(modbus_logging)

client = ModbusClient.ModbusSerialClient(
    config.get("modbus", "device"),
    framer=config.get("modbus", "framer"),
    baudrate=config.getint("modbus", "baudrate"),
    bytesize=config.getint("modbus", "bytesize"),
    parity=config.get("modbus", "parity"),
    stopbits=config.getint("modbus", "stopbits"),
    handle_local_echo=config.getboolean("modbus", "handle_local_echo", fallback=False),
    timeout=config.getint("modbus", "timeout"),
    retries=config.getint("modbus", "retries", fallback=3),
)
client.connect()
print("Connected to Modbus", file=sys.stderr)

def from_T1(registers):
    return (registers[0])

def from_T2(registers):
    buv = registers[0]
    if (buv & 0x8000):
        buv = -0x10000 + buv
    return buv

def from_T3(registers):
    buv = (registers[0] << 16) + registers[1]
    if (buv & 0x80000000):
        buv = -0x100000000 + buv
    return buv

def from_T5(registers):
    buv = ((registers[0] & 0x00FF) << 16) + registers[1]
    exp = (registers[0] & 0xFF00) >> 8
    if (exp & 0x80):
        exp = -0x100 + exp
    return buv * math.pow(10, exp)

def from_T6(registers):
    buv = ((registers[0] & 0x00FF) << 16) + registers[1]
    if (buv & 0x00800000):
        buv = -0x01000000 + buv
    exp = (registers[0] & 0xFF00) >> 8
    if (exp & 0x80):
        exp = -0x100 + exp
    return buv * math.pow(10, exp)

def from_T_float(registers):
    print(registers)
    [val] = struct.unpack('f', registers[0].to_bytes(2, 'big') + registers[1].to_bytes(2, 'big'))
    return val

def from_modbus_float(registers):
    return client.convert_from_registers(registers, client.DATATYPE.FLOAT32)

registers = {
    "finder": (
        (105, 2, from_T5, "frequency", "Hz", 1),
        (107, 2, from_T5, "voltage", "V", 1),
        #(126, 2, from_T5, "current", "A", 1), 
        (140, 2, from_T6, "power_active", "W", 1),
        #(148, 2, from_T6, "power_reactive", "var", 1),
        #(156, 2, from_T5, "power_apparent", "VA", 1),
        #(405, 1, from_T1, "tariff", "", 1),
        (462, 2, from_T3, "counter_n1", "Wh", 0.1), # x 0.1 Wh
        (464, 2, from_T3, "counter_n2", "Wh", 0.1), # x 0.1 Wh
        (466, 2, from_T3, "counter_n3", "varh", 0.1), # x 0.1 Wh
        (468, 2, from_T3, "counter_n4", "varh", 0.1), # x 0.1 Wh
    ),
    "taiyedq": ( # Does not support multiregister read
        (0x00, 2, from_modbus_float, "voltage", "V", 1),
        #(0x06, 2, from_modbus_float, "current", "A", 1),
        (0x0C, 2, from_modbus_float, "power_active", "W", 1),
        #(0x12, 2, from_modbus_float, "power_reactive", "var", 1),
        #(0x18, 2, from_modbus_float, "power_apparent", "VA", 1),
        (0x30, 2, from_modbus_float, "frequency", "Hz", 1),
        (0x500, 2, from_modbus_float, "counter_n1", "Wh", 1000.0),
        (0x502, 2, from_modbus_float, "counter_n2", "Wh", 1000.0),
        (0x508, 2, from_modbus_float, "counter_n3", "varh", 1000.0),
        (0x50A, 2, from_modbus_float, "counter_n4", "varh", 1000.0),
    ),
    "eastron": (
        (0, 2, from_modbus_float, "voltage", "V", 1),
        #(6, 2, from_modbus_float, "current", "A", 1),
        (12, 2, from_modbus_float, "power_active", "W", 1),
        #(24, 2, from_modbus_float, "power_reactive", "var", 1),
        #(18, 2, from_modbus_float, "power_apparent", "VA", 1),
        (70, 2, from_modbus_float, "frequency", "Hz", 1),
        (72, 2, from_modbus_float, "counter_n1", "Wh", 1000.0),
        (74, 2, from_modbus_float, "counter_n2", "Wh", 1000.0),
        (76, 2, from_modbus_float, "counter_n3", "varh", 1000.0),
        (78, 2, from_modbus_float, "counter_n4", "varh", 1000.0),
    ),
}

# Accelerated retrieving of basic metrics
def get_metrics_finder(client, meterAddr):
    m = ""
    val = client.read_input_registers(address=105, count=4, device_id=meterAddr)
    if (not val.isError()):
        value = from_T5(val.registers[0:2])
        m += "powermeter_%s{address=\"%03u\"} %g\n" % ("frequency", meterAddr, value)
        value = from_T5(val.registers[2:4])
        m += "powermeter_%s{address=\"%03u\"} %g\n" % ("voltage", meterAddr, value)
    val = client.read_input_registers(address=140, count=2, device_id=meterAddr)
    if (not val.isError()):
        value = from_T6(val.registers)
        m += "powermeter_%s{address=\"%03u\"} %g\n" % ("power_active", meterAddr, value)
    val = client.read_input_registers(address=462, count=8, device_id=meterAddr)
    if (not val.isError()):
        value = from_T3(val.registers[0:2]) * 0.1
        m += "powermeter_%s{address=\"%03u\"} %g\n" % ("counter_n1", meterAddr, value) # Import active energy
        value = from_T3(val.registers[2:4]) * 0.1
        m += "powermeter_%s{address=\"%03u\"} %g\n" % ("counter_n2", meterAddr, value) # Export active energy
        value = from_T3(val.registers[4:6]) * 0.1
        m += "powermeter_%s{address=\"%03u\"} %g\n" % ("counter_n3", meterAddr, value) # Import reactive energy
        value = from_T3(val.registers[6:8]) * 0.1
        m += "powermeter_%s{address=\"%03u\"} %g\n" % ("counter_n4", meterAddr, value) # Export reactive energy
    return m
    
# Accelerated retrieving of basic metrics
def get_metrics_eastron(client, meterAddr):
    m = ""
    val = client.read_input_registers(address=0, count=2, device_id=meterAddr)
    if (not val.isError()):
        value = from_modbus_float(val.registers)
        m += "powermeter_%s{address=\"%03u\"} %g\n" % ("voltage", meterAddr, value)
    val = client.read_input_registers(address=12, count=2, device_id=meterAddr)
    if (not val.isError()):
        value = from_modbus_float(val.registers)
        m += "powermeter_%s{address=\"%03u\"} %g\n" % ("power_active", meterAddr, value)
    val = client.read_input_registers(address=70, count=10, device_id=meterAddr)
    if (not val.isError()):
        value = from_modbus_float(val.registers[0:2]) * 1.0
        m += "powermeter_%s{address=\"%03u\"} %g\n" % ("frequency", meterAddr, value)
        value = from_modbus_float(val.registers[2:4]) * 1000.0
        m += "powermeter_%s{address=\"%03u\"} %g\n" % ("counter_n1", meterAddr, value) # Import active energy
        value = from_modbus_float(val.registers[4:6]) * 1000.0
        m += "powermeter_%s{address=\"%03u\"} %g\n" % ("counter_n2", meterAddr, value) # Export active energy
        value = from_modbus_float(val.registers[6:8]) * 1000.0
        m += "powermeter_%s{address=\"%03u\"} %g\n" % ("counter_n3", meterAddr, value) # Import reactive energy
        value = from_modbus_float(val.registers[8:10]) * 1000.0
        m += "powermeter_%s{address=\"%03u\"} %g\n" % ("counter_n4", meterAddr, value) # Export reactive energy
    return m    

def get_metrics():
    start = time.time()
    m = "# HELP powermeter_frequency AC frequency [Hz]\n" \
        "# TYPE powermeter_frequency gauge\n" \
        "# HELP powermeter_voltage Phase to neutral AC voltage [V]\n" \
        "# TYPE powermeter_voltage gauge\n" \
        "# HELP powermeter_current Current [A]\n" \
        "# TYPE powermeter_current gauge\n" \
        "# HELP powermeter_power_active Active power [W]\n" \
        "# TYPE powermeter_power_active gauge\n" \
        "# HELP powermeter_power_reactive Reactive power [var]\n" \
        "# TYPE powermeter_power_reactive gauge\n" \
        "# HELP powermeter_power_apparent Apparent power [VA]\n" \
        "# TYPE powermeter_power_apparent gauge\n" \
        "# HELP powermeter_counter_n1 Energy counter n1 state\n" \
        "# TYPE powermeter_counter_n1 counter\n" \
        "# HELP powermeter_counter_n2 Energy counter n2 state\n" \
        "# TYPE powermeter_counter_n2 counter\n" \
        "# HELP powermeter_counter_n3 Energy counter n3 state\n" \
        "# TYPE powermeter_counter_n3 counter\n" \
        "# HELP powermeter_counter_n4 Energy counter n4 state\n" \
        "# TYPE powermeter_counter_n4 counter\n" \
        "# TYPE powermeter_meas_time gauge\n";
    for meterAddrStr in config.options("meters"):
        meterType = config.get("meters", meterAddrStr);
        meterAddr = int(meterAddrStr)
        print("Querying device %u" % meterAddr, file=sys.stderr)
        try:
            lstart = time.time()
            if meterType == "finder":
                m += get_metrics_finder(client, meterAddr)
            elif meterType == "eastron":
                m += get_metrics_eastron(client, meterAddr)
            else:
                for register in registers[meterType]:
                    val = client.read_input_registers(address=register[0], count=register[1], device_id=meterAddr)
                    if (not val.isError()):
                        value = (register[2])(val.registers) * register[5]
                        line = "powermeter_%s{address=\"%03u\"} %g\n" % (register[3], meterAddr, value)
                        m += line
            lend = time.time()
            ltimeline = "powermeter_meas_time{address=\"%03u\"} %g\n" % (meterAddr, lend - lstart)
            print(ltimeline, file=sys.stderr)
            m += ltimeline
        except ModbusException:
            print("Device %u is not responding" % meterAddr, file=sys.stderr)    
    end = time.time()
    m += "powermeter_meas_time %g\n" % (end - start)
    print("\tDone", file=sys.stderr)
    return m

class MetricHttpRequestHandler(http.server.SimpleHTTPRequestHandler):
	def log_message(self, format, *args):
        if self.logging:
            SimpleHTTPServer.SimpleHTTPRequestHandler.log_message(self, format, *args)
	
    def do_GET(self):
        if self.path == '/metrics':
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            content = get_metrics()
            self.wfile.write(bytes(content, "utf8"))
        else:
            self.send_response(404)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            content = "Not found"
            self.wfile.write(bytes(content, "utf8"))
        return 

try:
    metrics_handler = MetricHttpRequestHandler
    metrics_handler.logging=config.getboolean("server", "logging", fallback=False)
    metrics_port = config.getint("server", "port")
    print("Binding metrics server to %u" % metrics_port, file=sys.stderr)
    socketserver.TCPServer.allow_reuse_address = True
    metrics_server = socketserver.TCPServer(("", metrics_port), metrics_handler)
    metrics_server.serve_forever()
except KeyboardInterrupt:
    pass
            
client.close()
print("Finished", file=sys.stderr)
