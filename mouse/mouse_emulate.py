#!/usr/bin/python3

import os
import sys
import dbus
import dbus.service
import dbus.mainloop.glib
import redis
import numpy as np
import time
import json

class MouseClient():

	def __init__(self):
		super().__init__()
		self.state = [0, 0, 0, 0]
		self.bus = dbus.SystemBus()
		self.btkservice = self.bus.get_object(
			'org.npl.btkbservice', '/org/npl/btkbservice')
		self.iface = dbus.Interface(self.btkservice, 'org.npl.btkbservice')
		self.r = redis.Redis('192.168.150.2')
		self.bluetooth_cursor_on = True
		self.bluetooth_click_on = True
		self.bluetooth_screen_height = 1964
		self.old_supergraph_id = None
	def send_current(self):
		try:
			self.iface.send_mouse(0, bytes(self.state))
		except OSError as err:
			error(err)

	def load_supergraph(self):
		supergraph_entries = self.r.xrevrange("supergraph_stream", count=1)

		# Parse the result from redis.
		supergraph_id, supergraph_entry = supergraph_entries[0]
		supergraph_bytes = supergraph_entry[b"data"]
		supergraph_str = supergraph_bytes.decode()
		supergraph_dict = json.loads(supergraph_str)

		# If this is a new supergraph, update this class's version.
		if supergraph_id != self.old_supergraph_id:
			self.old_supergraph_id = supergraph_id
			# Also grab the parameters for this specific node.
			matching_node_dicts = [
				n
				for n in supergraph_dict["nodes"].values()
				if n["nickname"] == "cursor_2d_task"
			]
			if not matching_node_dicts:
				message = {"message": f"Bluetooth: No parameters entry in supergraph for node '{self.nickname}'"}
				self.r.xadd("console_logging", message)
			node_dict = matching_node_dicts[0]

			node_params = node_dict["parameters"]

			if node_params.get('bluetooth_cursor_on') is not None:
				self.bluetooth_cursor_on = bool(node_params['bluetooth_cursor_on'])
				self.bluetooth_click_on = bool(node_params['bluetooth_click_on'])
				self.bluetooth_screen_height = int(node_params['bluetooth_screen_height'])
	
	def run(self):
		
		self.input_stream = "cursor_2d_commands"
		self.discrete_input_stream = "decoded_gestures"
		self.last_input_entry_seen = "$"

		last_input_entries = self.r.xrevrange(self.input_stream, count=1)
		self.last_input_entry_seen = (
			last_input_entries[0][0] if len(last_input_entries) > 0 else "0-0"
		)

		last_discrete_input_entries = self.r.xrevrange(
			self.discrete_input_stream, count=1
		)
		self.last_discrete_input_entry_seen = (
			last_discrete_input_entries[0][0]
			if len(last_discrete_input_entries) > 0
			else "0-0"
		)
	
		while True:

			read_result = self.r.xread(
					{
						# replace "$" with self.last_input_entry_seen, but gets bogged down
						self.input_stream: self.last_input_entry_seen,
						self.discrete_input_stream: self.last_discrete_input_entry_seen,
					}, count=1, block=0
				)
			
			x_final = 0
			y_final = 0

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

				x = int(x_bgcoordinates * self.bluetooth_screen_height)
				y = int(y_bgcoordinates * self.bluetooth_screen_height)

				if (x < 0):
					x = 256 + x

				if (y > 0):
					y = 256 - y

				if (y < 0):
					y = -1*y

				x_final += x
				y_final += y

				#print(x_final,y_final)

			for (
				discrete_input_entry_id,
				discrete_input_entry_dict,
			) in read_result_dict.get(self.discrete_input_stream, []):
				# Save that we've now seen this entry.
				self.last_discrete_input_entry_seen = discrete_input_entry_id

				# Discrete action command received.
				output_class = discrete_input_entry_dict[b"output_class"].decode()

				self.load_supergraph()

				# Ignore it if it is the null action.
				if output_class != "no_action" and self.bluetooth_click_on:
					self.state[0] = 1
					self.state[1] = 0
					self.state[2] = 0
					self.send_current()
					self.state[0] = 0
					self.send_current()

			self.load_supergraph()

			if self.bluetooth_cursor_on:
				self.state[1] = int(x_final)
				self.state[2] = int(y_final)

				self.send_current()
			
			# time.sleep(0.01)


if __name__ == "__main__":
	node = MouseClient()
	node.run()
