#!/usr/bin/python3

import os
import sys
import dbus
import dbus.service
import dbus.mainloop.glib
import redis
import numpy as np
import time

class MouseClient():

	def __init__(self):
		super().__init__()
		self.state = [0, 0, 0, 0]
		self.bus = dbus.SystemBus()
		self.btkservice = self.bus.get_object(
			'org.npl.btkbservice', '/org/npl/btkbservice')
		self.iface = dbus.Interface(self.btkservice, 'org.npl.btkbservice')
	def send_current(self):
		try:
			self.iface.send_mouse(0, bytes(self.state))
		except OSError as err:
			error(err)
	
	def run(self):
		
		self.input_stream = "cursor_2d_commands"
		self.discrete_input_stream = "decoded_gestures"
		self.last_input_entry_seen = "$"
		self.screen_height = 1964
		self.r = redis.Redis('192.168.150.2')

		last_input_entries = self.r.xrevrange(self.input_stream, count=1)
		self.last_input_entry_seen = (
			last_input_entries[0][0] if len(last_input_entries) > 0 else "0-0"
		)

		last_discrete_input_entries = self.r.xrevrange(
			self.discrete_input_stream, count=1
		)
		last_discrete_input_entry_seen = (
			last_discrete_input_entries[0][0]
			if len(last_discrete_input_entries) > 0
			else "0-0"
		)
	
		while True:
			
			read_result = self.r.xread(
                    {
                        self.input_stream: "$",
						self.discrete_input_stream: last_discrete_input_entry_seen,
                    }, count=1, block=0
                )

			read_result_dict = {
				stream.decode(): entries for stream, entries in read_result
			}

			for input_entry_id, input_entry_dict in read_result_dict.get(
				self.input_stream, []
			):
				# Save that we've now seen this entry.
				self.last_input_entry_seen = input_entry_id

				# Input command received.
				distance_bgcoordinates = np.frombuffer(
					input_entry_dict[b"data"], dtype=np.float32
				)
				x_bgcoordinates = distance_bgcoordinates[0]
				y_bgcoordinates = distance_bgcoordinates[1]

				x_final = int(x_bgcoordinates * self.screen_height)
				y_final = int(y_bgcoordinates * self.screen_height)

				if (x_final < 0):
					x_final = 256 + x_final

				if (y_final > 0):
					y_final = 256 - y_final

				if (y_final < 0):
					y_final = -1*y_final

				#print(x_final,y_final)

				self.state[1] = int(x_final)
				self.state[2] = int(y_final)

				self.send_current()

			for (
				discrete_input_entry_id,
				discrete_input_entry_dict,
			) in read_result_dict.get(self.discrete_input_stream, []):
				# Save that we've now seen this entry.
				last_discrete_input_entry_seen = discrete_input_entry_id

				# Discrete action command received.
				output_class = discrete_input_entry_dict[b"output_class"].decode()

				# Ignore it if it is the null action.
				if output_class != "no_action":
					self.state[0] = 1
					self.state[1] = 0
					self.state[2] = 0
					self.send_current()
					self.state[0] = 0

			time.sleep(0.01)


if __name__ == "__main__":
	node = MouseClient()
	node.run()
