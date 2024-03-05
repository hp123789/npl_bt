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
		self.run_mouse = True
		self.run_click = True
		self.screen_height = 1964
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
				if n["nickname"] == "brainToText_personalUse"
			]
			if not matching_node_dicts:
				message = {"message": f"Bluetooth: No parameters entry in supergraph for node '{self.nickname}'"}
				self.r.xadd("console_logging", message)
			node_dict = matching_node_dicts[0]

			node_params = node_dict["parameters"]

			if node_params.get('run_mouse') is not None:
				self.run_mouse = bool(node_params['run_mouse'])
				self.run_click = bool(node_params['run_click'])
				self.screen_height = int(node_params['screen_height'])
	
	def run(self):
		directions = {"left": "←",
				"right": "→",
				"up": "↑",
				"down": "↓",
				"down_left": "↙",
				"down_right": "↘",
				"up_left": "↖",
				"up_right": "↗"}
		
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
		last_discrete_input_entry_seen = (
			last_discrete_input_entries[0][0]
			if len(last_discrete_input_entries) > 0
			else "0-0"
		)
	
		while True:

			# try:
			# 	self.load_supergraph()
			# except Exception as e:
			# 	self.r.xadd("console_logging", "mouse supergraph error: " + e)

			if self.run_mouse:
			
				read_result = self.r.xread(
						{
							# replace "$" with self.last_input_entry_seen, but gets bogged down
							self.input_stream: self.last_input_entry_seen,
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

					if self.run_click:

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
								self.send_current()
				
				# time.sleep(0.01)


if __name__ == "__main__":
	node = MouseClient()
	node.run()
