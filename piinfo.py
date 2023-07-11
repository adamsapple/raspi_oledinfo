#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from dataclasses import dataclass
import subprocess
import sys
import signal
import time
import re
import ipget
import psutil
import socket
import datetime
import board
from busio import I2C
from adafruit_ssd1306 import SSD1306_I2C
from PIL import Image, ImageDraw, ImageFont


##
# Config.
#
DISPLAY_LENGTH  = 16          # OLED Word Count.
UPDATE_INTERVAL = 3           # info update interval.
NETWORK_INTERFACE = "wlan0"   # put ip from this network interface.
IS_PUT_RULER    = True        # 
FONT_PATH       = "/usr/share/fonts/truetype/noto/NotoMono-Regular.ttf"
OLED_WIDTH		= 128
OLED_HEIGHT		= 64

##
# Nodeの状態を表す
#
@dataclass
class Stats:
	hostname: str = 'unknown'
	ip: str = ''
	temp: float = 0.0
	cpu: float = 0.0
	usedMem: float = 0.0
	totalMem: float = 0.0
	usedMemPercent:float = 0.0
	diskUseGB: float = 0.0
	diskTotalGB: float = 0.0

	UPDATE_INTERVAL  = 0
	NETWORK_INTERFACE = ""

	##
	#
	#
	def __init__(self, update_interval, network_interface):
		self.UPDATE_INTERVAL   = update_interval
		self.NETWORK_INTERFACE = network_interface
		self.updateForce()


	##
	#
	#
	def update(self):
		self.updateIp()
		self.updateCpu(interval = self.UPDATE_INTERVAL)
		self.updateTemp()
		self.updateMem()
		self.updateDisk()
		self.updateHostname()
	

	##
	#
	#
	def updateForce(self):
		self.updateIp()
		self.updateCpu()
		self.updateTemp()
		self.updateMem()
		self.updateDisk()
		self.updateHostname()

	##
	#
	#
	def updateDisk(self):
		dsk = self.getDiskInfo()
		self.diskUseGB   = dsk['used' ] /1024/1024/1024
		self.diskTotalGB = dsk['total'] /1024/1024/1024

	##
	#
	#
	def getDiskInfo(self):
		disks = {}
		for partition in psutil.disk_partitions():
			path = partition.mountpoint
			dsk  = psutil.disk_usage(path=path)
			disks[path] = {'path': path, 'used': 0, 'total': 0}
			disks[path]['used']  = dsk.used
			disks[path]['total'] = dsk.total
	
		usedAll  = sum( x['used']  for x in disks.values())
		totalAll = sum( x['total'] for x in disks.values())
		
		return {'used': usedAll, 'total': totalAll}

	##
	#
	#
	def updateCpu(self, interval = None):
		self.cpu = psutil.cpu_percent(interval=interval)
		#self.cpu = psutil.cpu_percent(interval=None)
		#self.cpu = psutil.cpu_percent(interval=1)
	
	##
	#
	#
	def updateMem(self):
		mem = psutil.virtual_memory()
		self.usedMemPercent = mem.percent
		#self.usedMem       = mem.used  /1024/1024/1024
		self.usedMem        = (mem.total-mem.available) /1024/1024/1024
		self.totalMem       = mem.total /1024/1024/1024

	##
	#
	#
	def updateIp(self):
		self.ip = ipget.ipget().ipaddr(self.NETWORK_INTERFACE)
		self.ip = re.sub('/\d+', '', self.ip)

	##
	#
	#
	def updateTemp(self):
		with open("/sys/class/thermal/thermal_zone0/temp") as file:
			self.temp = float(file.read()) / 1000.0


	##
	#
	#
	def updateHostname(self):
		self.hostname = socket.gethostname()


##
# OLEDにレイアウトを合わせるクラス
#
class Aligner:
	DISPLAY_LENGTH: int = 16

	def __init__(self, display_length):
		self.DISPLAY_LENGTH = display_length

	##
	#
	#
	def formattedMsg(self, msg):
		length = len(msg)
		
		if length >= self.DISPLAY_LENGTH:
			return msg.replace('*', '')

		return re.sub('\*', ' ' * (self.DISPLAY_LENGTH - length + 1), msg)
 
	##
	#
	#
	def rightMsg(self, msg):
		length = len(msg)
		
		if length <=  self.DISPLAY_LENGTH:
			return msg
	
		return msg[length - self.DISPLAY_LENGTH:]


##
#
#
def GetCpuStats():
	cmd = "cat /proc/stat | grep cpu"
	res = subprocess.Popen(cmd, shell=True,
						 stdout=subprocess.PIPE,
						 stderr=subprocess.PIPE,
						 universal_newlines=True)
	Rstdout,Rstderr = res.communicate()
	#  行ごとに分割
	LineList = Rstdout.splitlines()
	Tcklist = []
	for line in LineList:
		ItemList = line.split()
		Idle = int(ItemList[4])
		Busy = int(ItemList[1]) + int(ItemList[2]) + int(ItemList[3])
		All = Busy + Idle
		Tcklist.append([ Busy, All ])

	return Tcklist


##
#
#
def putInfo(aligner, stats, ruler=False):
	if ruler == True:
		print("----+----+----+-")

	print(aligner.rightMsg("IP:%s" % stats.ip))
	print(aligner.formattedMsg('CPU:{:>3.0f}%'.format(stats.cpu) +  '*{:.1f}°c'.format(stats.temp)))
	print(aligner.formattedMsg('MEM:{:>3.0f}%'.format(stats.usedMemPercent) + "*%.1fGB" % (stats.totalMem)))
	print(aligner.formattedMsg('DSK:{:>4.0%}'.format(stats.diskUseGB / stats.diskTotalGB) + "*%.0fGB" % (stats.diskTotalGB))) 


@dataclass
class OledUtil:
	oled    = None
	image   = None
	draw    = None
	aligner = None
	font    = None
	tick:int  = 1

	##
	# ctor.
	#
	def __init__(self, width, height, i2c, address, aligner):
		# Make oled instance.
		self.oled = SSD1306_I2C(width, height, i2c, addr=address)
		
		# Make sure to create image with mode "1" for 1-bit color.
		self.image = Image.new("1", (self.oled.width, self.oled.height))

		# Get drawing object to draw on image.
		self.draw  = ImageDraw.Draw(self.image)

		self.aligner = aligner

	##
	#
	#
	def clear(self):
		# oled fill black.
		self.oled.fill(0)
		self.oled.show()


	##
	#
	#
	def flush(self):
		self.oled.image(self.image)
		self.oled.show()


	##
	# print information
	#
	def putInfo2Oled(self, stats):
		x = 0
		y = 0
		
		(fleft, ftop, fright, fbottom) = self.font.getbbox('A')
		font_height = fbottom - ftop + 1

		self.draw.rectangle((0, 0, self.oled.width, self.oled.height), outline=0, fill=0)
		
		self.tick += 1
		tick_color = 255 * (self.tick & 1)
		
		self.draw.rectangle((self.oled.width - 1 - 2, 0, self.oled.width-1, 2), outline=tick_color, fill=tick_color)

		#printOled("----+----+----+-", 0, 0)
		dt_now = datetime.datetime.now()
		self.printOled(dt_now.strftime('%m/%d %H:%M:%S'), 0, 0)
		y += font_height + 2

		self.printOled(self.aligner.rightMsg("IP:%s" % stats.ip), x, y)
		y += font_height + 2

		self.printOled(self.aligner.formattedMsg('CPU:{:>3.0f}%'.format(stats.cpu) +  '*{:.1f}°c'.format(stats.temp)), x, y)
		y += font_height + 2

		self.printOled(self.aligner.formattedMsg('MEM:{:>3.0f}%'.format(stats.usedMemPercent) + "*%.1fGB" % (stats.totalMem)), x, y)
		y += font_height + 2

		self.printOled(self.aligner.formattedMsg('DSK:{:>4.0%}'.format(stats.diskUseGB / stats.diskTotalGB) + "*%.0fGB" % (stats.diskTotalGB)), x, y)
		y += font_height + 2

		self.flush()


	##
	#
	#
	def printOled(self, text, x, y, color=255):
		self.draw.text(
			(x, y),
			text, font=self.font, fill=color)


	##
	# put splash.
	#
	def putSplashOled(self, stats):
		self.draw.rectangle((0, 0, self.oled.width-1, self.oled.height-1), outline=255, fill=255)
	
		#	Draw a smaller inner rectangle
		self.draw.rectangle((3, 3, self.oled.width - 3 - 1, self.oled.height - 3 - 1), outline=0, fill=0)

		# Draw Some Text
		text = "Hello!!"
		(fleft, ftop, fright, fbottom) = self.font.getbbox(text)
		font_width  = fright  - fleft + 1
		font_height = fbottom - ftop  + 1
		self.printOled(text, (self.oled.width - font_width) // 2, (self.oled.height - font_height) // 2 - font_height // 2)
		
		text = stats.hostname
		(fleft, ftop, fright, fbottom) = self.font.getbbox(text)
		font_width  = fright  - fleft + 1
		font_height = fbottom - ftop  + 1
		self.printOled(text, (self.oled.width - font_width) // 2, (self.oled.height - font_height) // 2 + font_height // 2)
		
		# Display image.
		self.flush()


##
# signal handler.
#
def handler(signum, frame):
	print("signal={}".format(signum))
	
	global sig_flag
	sig_flag = True


##
# main.
#
def main():
	signal.signal(signal.SIGTERM, handler)
	signal.signal(signal.SIGINT, handler)
	#signal.pause()
	
	stats = Stats(UPDATE_INTERVAL, NETWORK_INTERFACE)
	i2c   = I2C(sda=board.SDA, scl=board.SCL)
	
	global oledUtil
	oledUtil = OledUtil(OLED_WIDTH, OLED_HEIGHT, i2c, 0x3C, Aligner(DISPLAY_LENGTH))
	
	# oled fill black.
	oledUtil.flush()

	# Load default font.
	#font  = ImageFont.load_default()
	#font2 = ImageFont.truetype("/usr/share/fonts/opentype/noto/NotoSansCJK-DemiLight.ttc", 10)
	oledUtil.font = ImageFont.truetype(FONT_PATH, 13)

	oledUtil.putSplashOled(stats)

	# update information.
	while not sig_flag:
		stats.update()
		oledUtil.putInfo2Oled(stats)
		#putInfo(aligner, stats, ruler=IS_PUT_RULER)
		#time.sleep(UPDATE_INTERVAL)

	# terminate oled.
	oledUtil.clear()

##
# main.
#
oledUtil = None
sig_flag = False

if __name__ == "__main__":  
	try:
		main()

	except KeyboardInterrupt:
		print("Keyboard Interrupt detected.\nExit.")

	# except Exception as e:
	#   print("Unknown exception detected.\nExit.")
	#   print(e)

	finally:
		pass
