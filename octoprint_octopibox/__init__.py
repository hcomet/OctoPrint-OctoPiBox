# coding=utf-8
from __future__ import absolute_import

import octoprint.plugin
import octoprint.printer
from octoprint.util import RepeatedTimer
from octoprint.events import Events
import pigpio

# Main class used to interface with pigpio
class OctoPiBoxControl:

	def __init__(self, parent, printer_pin, spare_pin, printer_button_pin, spare_button_pin, debounce, powercallbackfunction):

		self._parent = parent
		self._pi = pigpio.pi()

		self._powercallbackfunction = powercallbackfunction

		self._common_init(printer_pin, spare_pin, printer_button_pin, spare_button_pin, debounce)

		self._powercallback = self._pi.callback(self._printer_pin, pigpio.EITHER_EDGE, self._powercallbackfunction)
		self._printerbuttoncallback = self._pi.callback(self._printer_button_pin, pigpio.FALLING_EDGE, self._buttoncallbackfunction)
		self._sparebuttoncallback = self._pi.callback(self._spare_button_pin, pigpio.FALLING_EDGE, self._buttoncallbackfunction)

		self._inited = True

	def _common_init(self, printer_pin, spare_pin, printer_button_pin, spare_button_pin, debounce):
		self._printer_pin = printer_pin
		self._spare_pin = spare_pin
		self._pi.set_mode(self._printer_pin, pigpio.OUTPUT)
		self._pi.set_mode(self._spare_pin, pigpio.OUTPUT)
		self._printer_button_pin = printer_button_pin
		self._spare_button_pin = spare_button_pin
		self._pi.set_mode(self._printer_button_pin, pigpio.INPUT)
		self._pi.set_pull_up_down(self._printer_button_pin, pigpio.PUD_UP)
		filter_error = self._pi.set_glitch_filter(self._printer_button_pin, debounce)
		if filter_error != 0:
			self._parent.logger.info("Glitch filter error. Pin: {}, Debounce: {}, Error: {}.".format(self._printer_button_pin, debounce, filter_error))

		self._pi.set_mode(self._spare_button_pin, pigpio.INPUT)
		self._pi.set_pull_up_down(self._spare_button_pin, pigpio.PUD_UP)
		filter_error = self._pi.set_glitch_filter(self._spare_button_pin, debounce)
		if filter_error != 0:
			self._parent.logger.info("Glitch filter error. Pin: {}, Debounce: {}, Error: {}.".format(self._spare_button_pin, debounce, filter_error))

	def _buttoncallbackfunction(self, gpio, level, tick):

		if gpio == self._printer_button_pin:
			if self._pi.read(self._printer_pin) == 1:
				self._pi.write(self._printer_pin, 0)
			else:
				self._pi.write(self._printer_pin, 1)

		elif gpio == self._spare_button_pin:
			if self._pi.read(self._spare_pin) == 1:
				self._pi.write(self._spare_pin, 0)
			else:
				self._pi.write(self._spare_pin, 1)

	def restart(self, printer_pin, spare_pin, printer_button_pin, spare_button_pin, debounce):

		self._powercallback.cancel()
		self._printerbuttoncallback.cancel()
		self._sparebuttoncallback.cancel()

		self._common_init(printer_pin, spare_pin, printer_button_pin, spare_button_pin, debounce)

		self._powercallback = self._pi.callback(self._printer_pin, pigpio.EITHER_EDGE, self._powercallbackfunction)
		self._printerbuttoncallback = self._pi.callback(self._printer_button_pin, pigpio.FALLING_EDGE, self._buttoncallbackfunction)
		self._sparebuttoncallback = self._pi.callback(self._spare_button_pin, pigpio.FALLING_EDGE, self._buttoncallbackfunction)

	def init_status_LED(self, red_pin, green_pin, blue_pin):
		self._status_red_pin = red_pin
		self._status_green_pin = green_pin
		self._status_blue_pin = blue_pin

		self.clear_status_LED()
		self._status_LED_colors = {
			"RED": 1<<self._status_red_pin,
			"GREEN": 1<<self._status_green_pin,
			"BLUE": 1<<self._status_blue_pin,
			"YELLOW": (1<<self._status_red_pin)+(1<<self._status_green_pin),
			"MAGENTA": (1<<self._status_red_pin)+(1<<self._status_blue_pin),
			"CYAN": (1<<self._status_blue_pin)+(1<<self._status_green_pin),
			"WHITE": (1<<self._status_red_pin)+(1<<self._status_green_pin)+(1<<self._status_blue_pin),
			"OFF": 0
		}

	def restart_status_LED(self, red_pin, green_pin, blue_pin):
		old_status_LED_state = self._status_LED_state;
		self.init_status_LED( red_pin, green_pin, blue_pin)
		self.set_status_LED_color( old_status_LED_state[0], old_status_LED_state[1], old_status_LED_state[2])

	def clear_status_LED(self):
		self._pi.wave_tx_stop()
		self._pi.wave_clear()
		self.pin_off(self._status_red_pin)
		self.pin_off(self._status_green_pin)
		self.pin_off(self._status_blue_pin)
		self._status_LED_state = [ "OFF", "OFF", "OFF"]

	def set_status_LED_color(self, color1, color2, blink_rate):
		blink_flash = []

		if blink_rate =="FAST":
			blink_ms = 100000
		elif blink_rate == "SLOW":
			blink_ms = 500000
		else:
			blink_ms = 1000000
			color2 = color1
			blink_rate = "OFF"

		step1_on_pins = self._status_LED_colors[color1]
		step1_off_pins = self._status_LED_colors[color1] ^ self._status_LED_colors["WHITE"]
		step2_on_pins = self._status_LED_colors[color2]
		step2_off_pins = self._status_LED_colors[color2] ^ self._status_LED_colors["WHITE"]

		blink_flash.append(pigpio.pulse(step1_on_pins,step1_off_pins,blink_ms))
		blink_flash.append(pigpio.pulse(step2_on_pins,step2_off_pins,blink_ms))

		self._pi.wave_add_generic(blink_flash)
		self._status_LED_wave = self._pi.wave_create()
		self._pi.wave_send_repeat(self._status_LED_wave)
		self._status_LED_state = [ color1, color2, blink_rate]

	def pin_on( self, pin):
		self._pi.write( pin, 1)

	def pin_off( self, pin):
		self._pi.write( pin, 0)

	def pin_value( self, pin):
		return self._pi.read( pin)

	def cancel(self):
		if self._inited:
			self._inited = False
			self._powercallback.cancel()
			self._printerbuttoncallback.cancel()
			self._sparebuttoncallback.cancel()
			self._pi.stop()




class OctoPiBoxPlugin(octoprint.plugin.TemplatePlugin,
							  octoprint.plugin.AssetPlugin,
							  octoprint.plugin.SimpleApiPlugin,
							  octoprint.plugin.EventHandlerPlugin,
							  octoprint.plugin.SettingsPlugin,
							  octoprint.plugin.StartupPlugin):

	def get_settings_defaults(self):
		return dict(
			enabled=False,
			timer_seconds=600,
			printer_pin=17,
			spare_pin=4,
			printer_button_pin=6,
			printer_button_enable_pin=18,
			spare_button_pin=5,
			spare_button_enable_pin=27,
			button_debounce=200,
			status_red_pin=22,
			status_green_pin=23,
			status_blue_pin=24 )

	def on_settings_save(self, data):
		octoprint.plugin.SettingsPlugin.on_settings_save(self, data)

		self._load_settings()

		self._octopibox.restart( self._printer_pin, self._spare_pin, self._printer_button_pin, self._spare_button_pin, self._button_debounce)
		self._octopibox.restart_status_LED(self._status_red_pin, self._status_green_pin, self._status_blue_pin)

	def on_after_startup(self):
		self._timeout_value = None
		self._timer = None

		self._load_settings()

		self._octopibox = OctoPiBoxControl(self, self._printer_pin, self._spare_pin, self._printer_button_pin, self._spare_button_pin, self._button_debounce, self._powercallbackfunction)
		self._update_power_status()
		self._octopibox.pin_on(self._printer_button_enable_pin)
		self._octopibox.pin_on(self._spare_button_enable_pin)
		self._octopibox.init_status_LED(self._status_red_pin, self._status_green_pin, self._status_blue_pin)
		self._set_status_LED("DISCONNECTED")

	def on_shutdown(self):
		self._octopibox.pin_off(self._printer_button_enable_pin)
		self._octopibox.pin_off(self._spare_button_enable_pin)
		self._octopibox.clear_status_LED()
		self._octopibox.cancel()

	def get_assets(self):
		return dict(js=["js/octopibox.js"])

	def get_template_configs(self):
		return [
			dict(type="settings",
			name="OctoPiBox Configuration",
			custom_bindings=False)
			]

	def get_api_commands(self):
		return dict(enable=[],
			disable=[],
			abort=[])

	def on_api_command(self, command, data):
		import flask
		if command == "abort":
			self._timer.cancel()
			self._timer = None
			self._set_status_LED("CONNECTED")
			self._logger.info("Automatic Power-Off aborted.")

	def on_event(self, event, payload):
		#self._logger.info("Event triggered: {}".format(event))
		if event == Events.PRINT_DONE:
			self._octopibox.pin_on(self._printer_button_enable_pin)
			if not self._enabled:
				self._logger.info("Print complete. Automatic Printer Power-off is currently DISABLED.")
				self._set_status_LED("CONNECTED")
				return
			if self._timer is not None:
				return

			self._timeout_value = self._settings.get_int(['timer_seconds'])
			if (self._timeout_value < 30) | (self._timeout_value > 1800):
				self._timeout_value = 600

			self._logger.info("Print complete. Automatic Printer Power-off is ENABLED. Starting timer.")
			self._set_status_LED("POWERINGOFF")
			self._timer = RepeatedTimer(1, self._timer_task)
			self._timer.start()
			self._plugin_manager.send_plugin_message(self._identifier, dict(type="timeout", timeout_value=self._timeout_value))
		elif event == Events.CONNECTED:
			self._set_status_LED("CONNECTED")
		elif event == Events.DISCONNECTED:
			self._set_status_LED("DISCONNECTED")
		elif event == Events.PRINT_STARTED:
			self._octopibox.pin_off(self._printer_button_enable_pin)
			self._set_status_LED("PRINTING")
		elif event == Events.PRINT_FAILED:
			self._octopibox.pin_on(self._printer_button_enable_pin)
			self._set_status_LED("ERROR")
		elif event == Events.PRINT_CANCELLED:
			self._octopibox.pin_on(self._printer_button_enable_pin)
			self._set_status_LED("ERROR")
		elif event == Events.CLIENT_OPENED:
			self._update_power_status()

	def _load_settings(self):
		self._enabled = self._settings.get_boolean(['enabled'])
		self._printer_pin = self._settings.get_int(['printer_pin'])
		self._spare_pin = self._settings.get_int(['spare_pin'])
		self._printer_button_pin = self._settings.get_int(['printer_button_pin'])
		self._printer_button_enable_pin = self._settings.get_int(['printer_button_enable_pin'])
		self._spare_button_pin = self._settings.get_int(['spare_button_pin'])
		self._spare_button_enable_pin = self._settings.get_int(['spare_button_enable_pin'])
		self._button_debounce = self._settings.get_int(['button_debounce'])
		self._status_red_pin = self._settings.get_int(['status_red_pin'])
		self._status_green_pin = self._settings.get_int(['status_green_pin'])
		self._status_blue_pin = self._settings.get_int(['status_blue_pin'])

	def _timer_task(self):
		self._timeout_value -= 1
		self._plugin_manager.send_plugin_message(self._identifier, dict(type="timeout", timeout_value=self._timeout_value))
		if self._timeout_value <= 0:
			self._timer.cancel()
			self._timer = None
			self._printeroff()

	def _powercallbackfunction(self, pin, level, tick):

		if pin == self._printer_pin:
			#self._logger.info("Printer pin {} level changed to {}".format(pin, level))
			self._update_power_status()
			if level == 0:
				current_connection = self._printer.get_current_connection()
				if current_connection[0] != "Closed":
					#self._logger.info("Printer connection found: {}".format(current_connection[0:3]))
					self._printer.disconnect()
					#self._logger.info("Printer disconnected after power-off.")
			elif level == 1:
				#self._logger.info("Printer power-on detected.")
				self._set_status_LED("CONNECTING")
				self._printer.connect()
				#self._logger.info("Printer auto-connect after power-on attempted.")

	def _printeroff(self):
		self._logger.info("Printer disconnect before power-off.")
		self._printer.disconnect()
		self._logger.info("Powering off printer on pin {}.".format( self._printer_pin))
		self._octopibox.pin_off(self._printer_pin)

		#self._logger.info("Powering off spare outlet on pin {}.".format( self._spare_pin))
		self._octopibox.pin_off(self._spare_pin)

	def _update_power_status(self):
		printer_power_status = ["Off", "On"]
		printer_power_status_text = printer_power_status[ self._octopibox.pin_value(self._printer_pin)]
		self._plugin_manager.send_plugin_message(self._identifier, dict(type="updatePowerStatus", power_status_value=printer_power_status_text))
		#self._logger.info("Data message sent from {} for power update to {}.".format(self._identifier, printer_power_status_text))

	def _set_status_LED(self, status="DISCONNECTED"):
		self._octopibox.clear_status_LED()
		if status=="DISCONNECTED":
			self._octopibox.set_status_LED_color("YELLOW", "OFF", "OFF")
		elif status == "CONNECTED":
			self._octopibox.set_status_LED_color("GREEN", "OFF", "OFF")
		elif status == "PRINTING":
			self._octopibox.set_status_LED_color("RED", "OFF", "OFF")
		elif status == "CONNECTING":
			self._octopibox.set_status_LED_color("GREEN", "YELLOW", "SLOW")
		elif status == "POWERINGOFF":
			self._octopibox.set_status_LED_color("RED", "YELLOW", "SLOW")
		elif status == "ERROR":
			self._octopibox.set_status_LED_color("RED", "OFF", "FAST")
		elif status == "OFF":
			self._octopibox.set_status_LED_color("OFF", "OFF", "OFF")
		else:
			self._octopibox.set_status_LED_color("OFF", "OFF", "OFF")

	##~~ Softwareupdate hook

	def get_update_information(self):
		# Define the configuration for your plugin to use with the Software Update
		# Plugin here. See https://github.com/foosel/OctoPrint/wiki/Plugin:-Software-Update
		# for details.
		return dict(
			octopibox=dict(
				displayName="OctoPiBox Plugin",
				displayVersion=self._plugin_version,

				# version check: github repository
				type="github_release",
				user="hcomet",
				repo="OctoPrint-OctoPiBox",
				current=self._plugin_version,

				# update method: pip
				pip="https://github.com/hcomet/OctoPrint-OctoPiBox/archive/{target_version}.zip"
			)
		)


# If you want your plugin to be registered within OctoPrint under a different name than what you defined in setup.py
# ("OctoPrint-PluginSkeleton"), you may define that here. Same goes for the other metadata derived from setup.py that
# can be overwritten via __plugin_xyz__ control properties. See the documentation for that.
__plugin_name__ = "OctoPiBox Plugin"

def __plugin_load__():
	global __plugin_implementation__
	__plugin_implementation__ = OctoPiBoxPlugin()

	global __plugin_hooks__
	__plugin_hooks__ = {
		"octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
	}
