#!/usr/bin/env python3

import os
import re
import json
from functools import partial
import socket
from ws4py.client.threadedclient import WebSocketClient

try:
	import tornado.httpserver
	import tornado.ioloop
	import tornado.web
	import tornado.websocket
	import tornado.template
	from tornado import locks, gen
	from tornado.platform.asyncio import AsyncIOMainLoop
	from tornado import gen
	from tornado.options import options, define
	from tornado.queues import Queue
except ImportError:
	print("Cannot import Tornado: Do `pip3 install --user tornado` to install")

# Global variables
atl_ide_debug_level = 1 # 0 = off, 1 = debug inflo, 2 = load debuggable blockly js
code = ""



class atl_IDE_webappserver_node(Node): # MODIFY NAME
	def __init__(self):
		super().__init__("atl_IDE_webappserver_node") # MODIFY NAME

		def atl_IDE_webappserver():
			msg = IDEWEBAPP()
			msg.debug_message = "IDE webserver running! I am listening at port " + str(self.get_parameter("webapp_port").value)
			self.IDEWEBAPP_status_publisher_.publish(msg)
			self.get_logger().info("Tornado IOLoop START, please use http://" + str(atl_webappserver_IP) + ":" +str(self.get_parameter("webapp_port").value) + " to connect!")
			tornado.ioloop.IOLoop.current().start()


		#	Tornado WEB Handlers - GET requests
		class IndexHandler(tornado.web.RequestHandler): # ATL IDE Langing page
			def initialize(self, path):
				self.path = path
			def get(self, path):
				print('self.path :' + str(self.path))
				self.render(self.path + 'index.html')
				if atl_ide_debug_level > 0:
					print("[DEBUG Level "+str(atl_ide_debug_level)+": Serving index.html form " + str(self.path))

		class ATLIDEWorkspaceHandler(tornado.web.RequestHandler):
			def initialize(self, path):
				self.path = path
			def get(self, path):
				blockly_extension_path = str(self.path)
				cozmo_blockly_path = str(blockly_extension_path) + 'cozmo-blockly/'
				thymio_blockly_path = str(blockly_extension_path) + 'thymio-blockly/'

				print("[DEBUG Level " + str(atl_ide_debug_level) + ": cozmo_blockly_path " + str(cozmo_blockly_path))
				print("[DEBUG Level " + str(atl_ide_debug_level) + ": thymio_blockly_path " + str(thymio_blockly_path))

				loader = tornado.template.Loader(cozmo_blockly_path, whitespace='all')
				file = 'includes.template'
				if atl_ide_debug_level > 1:
					file = 'includes_debug.template'
				t = loader.load(file)
				includes = t.generate()

				# Modularisation of the toolbox depending on the available robots
				loader = tornado.template.Loader(cozmo_blockly_path, whitespace='all')
				file = 'cozmo_blocks.xml'
				t = loader.load(file)
				cozmo_blocks = t.generate()

				loader = tornado.template.Loader(thymio_blockly_path, whitespace='all')
				file = 'thymio_blocks.xml'
				t = loader.load(file)
				thymio_blocks = t.generate()

				print('[Server] HomeHandler: Loading ' + cozmo_blockly_path + ' and ' + thymio_blockly_path)

				self.render(blockly_extension_path + 'index.html', includes=includes, cozmo_blocks=cozmo_blocks, thymio_blocks=thymio_blocks, name="Give Name")

		class SavesHandler(tornado.web.RequestHandler):
			def initialize(self, folder):
				self.folder = folder
			def get(self, folder, file):
				folder = self.folder
				file = file.strip('/')
				if len(file) == 0:
					# Send folder index
					storedFiles = []
					removeXmlRegex = re.compile('\.xml$')
					for filename in os.listdir(folder):
						relativePath = os.path.join(folder, filename)
						if os.path.isfile(relativePath) and filename.endswith('.xml'):
							storedFiles.append(removeXmlRegex.sub('', filename))
					print("Returning files list: " + str(storedFiles))
					self.write(json.dumps(storedFiles).encode('utf-8'))
					self.set_header('Content-type', 'application/json')
				else:
					# Send only one file
					f = open(os.path.join(folder, file + '.xml'), 'r')
					data = f.read()
					f.close()
					self.write(data)

			def put(self, folder, file):
				folder = self.folder
				file = file.strip('/')
				print('[Server] SavesHandler: Saving ' + file)
				data = self.request.body
				f = open(os.path.join(folder, file + '.xml'), 'wb')
				f.write(data)
				f.close()

		class RobotSubmitHandler(tornado.web.RequestHandler):
			@gen.coroutine
			def post(self):
				remote_ip = self.request.remote_ip
				data = self.request.body
				get_logger('RobotSubmitHandler').info('Receiving code: \n' + str(data) + "\n\nfrom " +str(remote_ip))
				try:
					code = str(data, 'utf-8')
					print('Received code: \n\n' + str(code) + '\n\n')
					target_bot = "TODO: Get target Bot"
					action = "RUN"
					call_session_manager_service(target_bot, remote_ip, code, action)
					call_python_code_executor_runcode_service(target_bot, remote_ip, code, action)
				except Exception as e:
					err = str(e)
					print('ERROR: \n\n' + str(err) + '\n\n')
					raise tornado.web.HTTPError(500, err, reason=err)

		class RobotTerminateHandler(tornado.web.RequestHandler):
			@gen.coroutine
			def post(self):
				remote_ip = self.request.remote_ip
				get_logger('RobotTerminateHandler').info('Request from ' + str(remote_ip) + " to terminate program")
				target_bot = "TODO: Get target Bot"
				action = "STOP"
				call_session_manager_service(target_bot, remote_ip, code, action)
#				tornado.ioloop.IOLoop.current().stop()

		class WSBlocksSubHandler(tornado.websocket.WebSocketHandler):
			def open(self):
				get_logger('WSBlocksSubHandler').info('WSBlocksSub client connected')
				self.application._blocks = self

			def on_close(self):
				get_logger('WSBlocksSubHandler').info('WSBlocksSub client disconnected')

			def on_message(self, message):
				get_logger('WSBlocksSubHandler').info('WSBlocksSub client message: ' + message)
				# echo message back to client
				self.write_message(message)

		class WSBlocksPubHandler(tornado.websocket.WebSocketHandler):
			def open(self):
				get_logger('WSBlocksSPub').info('WSBlocksSPub Handler client connected')

			def on_message(self, message):
				try:
					if self.application._blocks:
						self.application._blocks.write_message(message)
				except Exception:
					pass

			def on_close(self):
				print('[Server]  WSConsolePub client disconnected')

		class WS3dSubHandler(tornado.websocket.WebSocketHandler):
			def open(self):
				print('[Server] 3dSub client connected')
				self.application._ws3d = self

			def on_close(self):
				print('[Server] 3dSub client disconnected')

			def on_message(self, message):
				print('[Server] 3dSub client message: ' + message)
				# echo message back to client
				self.write_message(message)

		class WS3dPubHandler(tornado.websocket.WebSocketHandler):
			def open(self):
				print('[Server] 3dPub client connected')

			def on_message(self, message):
				try:
					if self.application._ws3d:
						self.application._ws3d.write_message(message)
				except Exception:
					pass

			def on_close(self):
				print('[Server] 3dPub client disconnected')


		class basicRequestHandler(tornado.web.RequestHandler):
			def get(self):
				self.write('Hello, world!!!!!!')

		# 	End of WebHandler definitions

		settings = {
			"gallery_path": str(atl_IDE_webappserver_install_dir) + 'gallery/',
			"webapp_root": str(atl_IDE_webappserver_install_dir),
			"static_path": str(atl_IDE_webappserver_install_dir),
			"saves_path": str(atl_IDE_webappserver_install_dir) + 'saves/',
			"cookie_secret": "61oETzKXQAGaYdkL5gEmGeJJFuYh7EQnp2XdTP1o/Vo=",
			'debug': True,
		}

		app = tornado.web.Application([
			(r'/()',IndexHandler , dict(path=settings['webapp_root'])),
			(r'/gallery/(.*)',tornado.web.StaticFileHandler, dict(path=settings['gallery_path'])),
			(r'/EN/()', ATLIDEWorkspaceHandler, dict(path=settings['blockly_extensions_path'])),
			(r'/FR/()', ATLIDEWorkspaceHandler, dict(path=settings['blockly_extensions_path'])),
			(r'/static/(.*)', tornado.web.StaticFileHandler, dict(path=settings['static_path'])),
			(r'/EN/(.+)', tornado.web.StaticFileHandler , dict(path=settings['blockly_extensions_path'])),
			(r'/FR/(.+)', tornado.web.StaticFileHandler , dict(path=settings['blockly_extensions_path'])),
			(r'/msg/(.*)', tornado.web.StaticFileHandler, dict(path=settings['blockly_path'])),
			(r'/(saves)/(.*)', SavesHandler , dict(folder=settings['saves_path'])),
		],**settings)

		app.listen(self.get_parameter("webapp_port").value)

		app._lock = locks.Lock()

def main(args=None):
# TODO
if __name__ == "__main__":
	main()
