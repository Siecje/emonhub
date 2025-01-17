import time
import datetime
import Cargo

try:
    from pymodbus.client.sync import ModbusSerialClient as ModbusClient
    pymodbus_found = True
except ImportError:
    pymodbus_found = False

from emonhub_interfacer import EmonHubInterfacer

"""class EmonModbusTcpInterfacer
Monitors Renogy Rover via USB RS232 Cable over modbus
"""

class EmonHubModbusRenogyInterfacer(EmonHubInterfacer):

    def __init__(self, name, com_port='/dev/ttyUSB0', com_baud=9600, toextract='', poll_interval=30):
        """Initialize Interfacer
        com_port (string): path to COM port
        """

        # Initialization
        super(EmonHubModbusRenogyInterfacer, self).__init__(name)
        self.poll_interval = int(poll_interval)
        self.last_read = time.time()

        if not pymodbus_found:
            self._log.error("PYMODBUS NOT PRESENT BUT NEEDED !!")
        # open connection
        if pymodbus_found:
            self._log.info("pymodbus installed")
            self._log.debug("EmonHubModbusRenogyInterfacer args: " + com_port + " - " + str(com_baud))

            self._con = self._open_modbus(com_port, com_baud)
            if self._con:
                self._log.info("Modbus client Connected!")
            else:
                self._log.info("Connection to Modbus client failed. Will try again later")

    def close(self):

        # Close TCP connection
        if self._con is not None:
            self._log.debug("Closing USB/Serial port")
        self._con.close()

    def _open_modbus(self, com_port, com_baud):
        """ Open connection to modbus device """
        BATTERY_TYPE = {
            1: 'open',
            2: 'sealed',
            3: 'gel',
            4: 'lithium',
            5: 'self-customized'
        }

        try:
            self._log.info("Starting Modbus client . . . ")
            c = ModbusClient(method='rtu', port=com_port, baudrate=com_baud, stopbits=1, bytesize=8, parity='N')
            if c.connect():
                Model = c.read_holding_registers(12, 8, unit=1)
                self._log.info("Connected to Renogy Model: " + str(Model.registers[0]))
                BatteryType = c.read_holding_registers(57348, 1, unit=1).registers[0]
                BatteryCapacity = c.read_holding_registers(57346, 1, unit=1).registers[0]
                self._log.info("Battery Type: " + BATTERY_TYPE[BatteryType] + " " + str(BatteryCapacity) + "ah")
                self._modcon = True
            else:
                self._log.debug("Connection failed")
                self._modcon = False
        except Exception as e:
            self._log.error("modbus connection failed" + str(e))
           #raise EmonHubInterfacerInitError('Could not open connection to host %s' %modbus_IP)
        else:
            return c

    def read(self):
        now = time.time()
        if not now - self.last_read > self.poll_interval:
            # Wait to read based on poll_interval
            return

        self.last_read = now

        # CHARGING_STATE = {
        #     0: 'deactivated',
        #     1: 'activated',
        #     2: 'mppt',
        #     3: 'equalizing',
        #     4: 'boost',
        #     5: 'floating',
        #     6: 'current limiting'
        # }

        """ Read registers from client"""
        if pymodbus_found:
            time.sleep(float(self._settings["interval"]))
            f = []
            c = Cargo.new_cargo(rawdata="")

            if not self._modcon:
                self._con.close()
                self._log.info("Not connected, retrying connect" + str(self.init_settings))
                self._con = self._open_modbus(self.init_settings["modbus_IP"], self.init_settings["modbus_port"])

            if self._modcon:

                # read battery registers
                BatteryPercent = self._con.read_holding_registers(256, 1, unit=1).registers[0]
                #Charging_Stage = CHARGING_STATE[self._con.read_holding_registers(288, 1, unit=1).registers[0]]
                Charging_Stage = self._con.read_holding_registers(288, 1, unit=1).registers[0]
                self._log.debug("Battery Percent " + str(BatteryPercent) + "%")
                self._log.debug("Charging Stage "  + str(Charging_Stage))

                Temp_raw = self._con.read_holding_registers(259, 2, unit=1)
                temp_value = Temp_raw.registers[0] & 0x0ff
                sign = Temp_raw.registers[0] >> 7
                BatteryTemp_C = -(temp_value - 128) if sign == 1 else temp_value
                BatteryTemp_F = (BatteryTemp_C * 9/5) + 32
                self._log.debug("BatteryTemp_C " + str(BatteryTemp_C))
                self._log.debug("BatteryTemp_F " + str(BatteryTemp_F))

                # read Solar registers
                SolarVoltage = self._con.read_holding_registers(263, 1, unit=1).registers[0]
                SolarCurrent = self._con.read_holding_registers(264, 1, unit=1).registers[0]
                SolarPower = self._con.read_holding_registers(265, 1, unit=1).registers[0]
                self._log.debug("SolarVoltage " + str(SolarVoltage) + "v")
                self._log.debug("SolarCurrent " + str(SolarCurrent) + "a")
                self._log.debug("SolarPower "   + str(SolarPower)   + "w")

                # Create a Payload object
                c = Cargo.new_cargo()

                if int(self._settings['nodeoffset']):
                    c.nodeid = int(self._settings['nodeoffset'])
                    c.realdata = [BatteryPercent, Charging_Stage, BatteryTemp_F, SolarVoltage, SolarCurrent, SolarPower]
                else:
                    self._log.error("nodeoffset needed in emonhub configuration, make sure it exists and is a integer ")

                self._log.debug("Return from read data: " + str(c.realdata))
                return c
