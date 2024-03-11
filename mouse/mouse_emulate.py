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
		self.r = redis.Redis('192.168.150.2', socket_timeout=5)
		self.bluetooth_cursor_off = False
		self.bluetooth_click_off = False
		self.bluetooth_px_per_bgunit = 1964
		self.old_supergraph_id = None
	def send_current(self):
		try:
			self.iface.send_mouse(0, bytes(self.state))
			self.r.xadd("bluetooth_cursor_commands", {"state": self.state})
		except OSError as err:
			error(err)

	def load_supergraph(self):
		supergraph_entries = self.r.xrevrange("supergraph_stream", count=1)

		if len(supergraph_entries) == 0:
			return False

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
				return False
			node_dict = matching_node_dicts[0]

			node_params = node_dict["parameters"]

			self.bluetooth_cursor_off = bool(node_params.get('bluetooth_cursor_off', False))
			self.bluetooth_click_off = bool(node_params.get('bluetooth_click_off', False))
			self.bluetooth_px_per_bgunit = int(node_params.get('bluetooth_px_per_bgunit', 1964))
		
		return True
	
	def reconnect_redis(self):
		isConnected = False
		while not isConnected:
			try:
				self.r.ping()
				t = self.r.time()
				self.last_input_entry_seen = int(t[0]*1000 + t[1]/1000)
				self.last_discrete_input_entry_seen = int(t[0]*1000 + t[1]/1000)
				isConnected = True
			except:
				pass
	
	def run(self):

		self.reconnect_redis()
		
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
			
			try:
				read_result = self.r.xread(
						{
							# replace "$" with self.last_input_entry_seen, but gets bogged down
							self.input_stream: self.last_input_entry_seen,
							self.discrete_input_stream: self.last_discrete_input_entry_seen,
						}, block=0
					)
				
				click_final = False
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

					x = int(x_bgcoordinates * self.bluetooth_px_per_bgunit)
					y = int(y_bgcoordinates * self.bluetooth_px_per_bgunit)

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

					# Ignore it if it is the null action.
					if output_class != "no_action":
						click_final = True

				self.load_supergraph()

				disable_bluetooth_click = self.bluetooth_click_off or self.r.get("task_state_current") == b'1'
				disable_bluetooth_cursor = self.bluetooth_cursor_off or self.r.get("task_state_current") == b'1'

				if x_final < 0: x_final = 0
				if x_final > 255: x_final = 255
				
				if y_final < 0: y_final = 0
				if y_final > 255: y_final = 255

				if not disable_bluetooth_click:
					if click_final:
						self.state[0] = 1
						self.state[1] = 0
						self.state[2] = 0
						self.send_current()
						self.state[0] = 0
						self.send_current()

				if not disable_bluetooth_cursor:
					self.state[1] = int(x_final)
					self.state[2] = int(y_final)

					self.send_current()
				
				# time.sleep(0.01)
					
			except redis.exceptions.TimeoutError:
				self.reconnect_redis()


if __name__ == "__main__":
	node = MouseClient()
	try:
		node.run()
	except Exception as e:
		message = {"message": "BLUETOOTH MOUSE ERROR: " + e}
		node.r.xadd("console_logging", message)
