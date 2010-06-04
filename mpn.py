#! /usr/bin/python
# -*- coding: utf-8 -*-

#     Copyright 2007-2008 Olivier Schwander <olivier.schwander@ens-lyon.org>

#     This program is free software; you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation; either version 2 of the License, or
#     (at your option) any later version.

#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.

#     You should have received a copy of the GNU General Public License
#     along with this program; if not, write to the Free Software
#     Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

# Requirements:
# You will need pygtk, python-notify, python-mpdclient and python-gtk2

# Usage:
# Simply launch ./mpn.py or ./mpn.py -h for usage help

"""Simple libnotify notifier for mpd"""

import os, sys, cgi
from optparse import Option, OptionParser, OptionGroup, SUPPRESS_HELP

import gobject
import gtk
import mpd
import pynotify
import re
import socket

format_title = "%t"
format_body = "<b>%b</b><br><i>%a</i>"
default_icon = "gnome-mime-audio"

MPN = None 
def convert_time(raw):
	"""Format a number of seconds to the hh:mm:ss format"""
	# Converts raw time to 'hh:mm:ss' with leading zeros as appropriate
        
	hour, minutes, sec = ['%02d' % c for c in (raw/3600,
	(raw%3600)/60, raw%60)]
        
	if hour == '00':
		if minutes.startswith('0'):
			minutes = minutes[1:]
		return minutes + ':' + sec
	else:
		if hour.startswith('0'):
			hour = hour[1:]
		return hour + ':' + minutes + ':' + sec

def prev_cb(n, action):
	if MPN.debug:
		print "Previous song"
	MPN.mpd.previous()
	if MPN.once:
		MPN.close()
		gtk.main_quit()

def next_cb(n, action):
	if MPN.debug:
		print "Next song"
	MPN.mpd.next()
	if MPN.once:
		MPN.close()
		gtk.main_quit()

class Notifier:
	"Main class for mpn"
	debug = False
	keys = False
	persist = False
	once = False
	refresh_time = 750 # in ms
	host = "localhost"
	port = 6600
	mpd = None
	status = None
	current = None
	notifier = None
	iterate_handler = None
	title_txt = None
	body_txt = None
	icon_url = None
	re_t = re.compile('(%t)', re.S) #Title
	re_a = re.compile('(%a)', re.S) #Artist
	re_b = re.compile('(%b)', re.S) #alBum
	re_d = re.compile('(%d)', re.S) #song Duration
	re_f = re.compile('(%f)', re.S) #File
	re_n = re.compile('(%n)', re.S) #track Number
	re_p = re.compile('(%p)', re.S) #playlist Position
        
	def get_host(self):
		"""get host name from MPD_HOST env variable"""
		host = os.environ.get('MPD_HOST', 'localhost')
		if '@' in host:
			return host.split('@', 1)
		return host
        
	def get_port(self):
		"""get host name from MPD_PORT env variable"""
		return os.environ.get('MPD_PORT', 6600)
        
	def get_title(self, safe=False):
		"""Get the current song title"""
		try:
			title = self.current["title"]
			#In case the file has a multi-title tag
			if type(title) is list:
				title = " - ".join(title)
		except KeyError:
			#Attempt to use filename
			title = self.get_file(safe)
			if title == "":
				title = "???"
		if self.debug:
			print "Title :" + title
		if safe:
			return cgi.escape(title)
		return title
	
	def get_time(self, elapsed=False):
		"""Get current time and total length of the current song"""
		time = self.status["time"]
		now, length = [int(c) for c in time.split(':')]
		now_time = convert_time(now)
		length_time = convert_time(length)
                
		if self.debug:
			print "Position : " + now_time + " / " + length_time
		if elapsed:
			return now_time
		return length_time
        
	def get_tag(self, tag, safe=False):
		"""Get a generic tag from the current data"""
		try:
			data = self.current[tag]
			#In case the file has a multi-value tag
			if type(data) is list:
				data = " / ".join(data)
		except KeyError:
			data = ""
		if self.debug:
			print tag + ": " + data
		if safe:
			return cgi.escape(data)
		return data 
        
	def get_file(self, safe=False):
		"""Get the current song file"""
		try:
			file = self.current["file"]
			# Remove left-side path
			file = re.sub(".*"+os.sep, "", file)
			# Remove right-side extension
			file = re.sub("(.*)\..*", "\\1", file)
		except KeyError:
			file = ""
		if self.debug:
			print "Filename: " + file
		if safe:
			return cgi.escape(file)
		return file
        
	def connect(self):
		try:
			self.mpd.connect(self.host, self.port)
			return True
		except mpd.socket.error:
			return False
		# Already connected
		except mpd.ConnectionError:
			return True 
        
	def disconnect(self):
		try:
			self.mpd.disconnect()
			return True
		except mpd.socket.error:
			return False
		except mpd.ConnectionError:
			return False
        
	def reconnect(self):
		# Ugly, but there's no mpd.isconnected() method
		self.disconnect()
		if self.persist:
			self.connect()
			return True
		else:
			print "mpn.py: Lost connection to server, exiting...\n"
			sys.exit(1)
			return False
        
	def notify(self):
		"""Display the notification"""
		try:
			self.status = self.mpd.status()
                        
			# only if there is a song currently playing
			if not self.status["state"] in ['play', 'pause']:
				if self.debug:
					print "No files playing on the server." + self.host
				return True
                        
			# only if the song has changed
			new_current = self.mpd.currentsong()
			if self.current == new_current:
				return True
			self.current = new_current
                        
			title = self.title_txt
			body = self.body_txt
			# get values with the strings html safe
			title = self.re_t.sub(self.get_title(), title)
			title = self.re_f.sub(self.get_file(), title)
			title = self.re_d.sub(self.get_time(), title)
			title = self.re_a.sub(self.get_tag('artist'), title)
			title = self.re_b.sub(self.get_tag('album'), title)
			title = self.re_n.sub(self.get_tag('track'), title)
			title = self.re_p.sub(self.get_tag('pos'), title)
                        
			body = self.re_t.sub(self.get_title(True), body)
			body = self.re_f.sub(self.get_file(True), body)
			body = self.re_d.sub(self.get_time(), body)
			body = self.re_a.sub(self.get_tag('artist', True), body)
			body = self.re_b.sub(self.get_tag('album', True), body)
			body = self.re_n.sub(self.get_tag('track'), body)
			body = self.re_p.sub(self.get_tag('pos'), body)
		except mpd.ConnectionError, (ce):
			return self.reconnect()
		except socket.error, (se):
			return self.reconnect()
                
		# set paramaters and display the notice
		if self.debug:
			print "Title string: " + title
			print "Body string: " + body
		self.notifier.update(title, body, self.icon_url)
		if not self.notifier.show():
			print "Impossible to display the notification"
			return False
                
		return True
        
	def run(self):
		"""Launch the iteration"""
		if (self.once):
			self.notify()
		else:
			self.iterate_handler = gobject.timeout_add(self.refresh_time, self.notify)
        
	def close(self):
		return self.disconnect()
        
	def __init__(self, debug=False, notify_timeout=3, show_keys=False,
		persist=False, once=False, title_format=None, body_format=None, icon=None):
		"""Initialisation of mpd client and pynotify"""
		self.debug = debug
		self.persist = persist
		self.once = once
		self.icon_url = icon
		# Contents are updated before displaying
		self.notifier = pynotify.Notification("MPN")
                
		# param notify_timeout is in seconds
		if notify_timeout == 0:
			self.notifier.set_timeout(pynotify.EXPIRES_NEVER)
		else:
			self.notifier.set_timeout(1000 * notify_timeout)
                
		if show_keys:
			self.notifier.add_action("back", "&lt;&lt;", prev_cb)
			self.notifier.add_action("forward", "&gt;&gt;", next_cb)
                
		self.title_txt = re.sub("<br>", "\n", title_format)
		self.body_txt = re.sub("<br>", "\n", body_format)
                
		if self.debug:
			print "Title format: " + self.title_txt
			print "Body format: " + self.body_txt
		self.host = self.get_host()
		self.port = self.get_port()
		self.mpd = mpd.MPDClient()
		if not self.connect():
			print "Impossible to connect to server " + self.host
			sys.exit(1)

if __name__ == "__main__":
	# initializate the argument parser
	PARSER = OptionParser()
        
	# help/debug mode
	PARSER.add_option("--debug", action="store_true", dest="debug",
		default=False, help="Turn on debugging information")
        
	# does mpn will fork ?
	PARSER.add_option("-d", "--daemon", action="store_true", dest="fork",
		default=False, help="Fork into the background")
        
	PARSER.add_option("-p", "--persist", action="store_true", dest="persist",
		default=False, help="Do not exit when connection fails")
        
	# how many time the notice will be shown
	PARSER.add_option("-t", "--timeout", type="int", dest="timeout", default=3,
		help="Notification timeout in secs (use 0 to disable)")
        
	# display next/prev keys on popup dialog
	PARSER.add_option("-k", "--keys", action="store_true", dest="keys",
		default=False, help="Add Prev/Next buttons to notify window")
        
	# whether to print updates on all song changes
	PARSER.add_option("-o", "--once", action="store_true", dest="once",
		default=False, help="Notify once and exit")
        
	PARSER.add_option("-i", "--icon", dest="default_icon", default=default_icon,
		help="Icon URI/name (default: %default)")
        
	# Format strings
	GROUP = OptionGroup(PARSER, "Format related options for the notify display",
		"Supported wildcards:"
		" %t title /"
		" %a artist /"
		" %b album /"
		" %d song duration /"
		" %f base filename /"
		" %n track number /"
		" %p playlist position /"
		" <i> </i> italic text /"
		" <b> </b> bold text /"
		" <br> line break")
        
	GROUP.add_option("-F", "--header", dest="title_format", default=format_title,
		help="Format for the notify header (default: %default)")
        
	GROUP.add_option("-f", "--format", dest="body_format", default=format_body,
		help="Format for the notify body (default: %default)")
        
	PARSER.add_option_group(GROUP)
        
	# parse the commandline
	(OPTIONS, ARGS) = PARSER.parse_args()
        
	# initializate the notifier
	if not pynotify.init('mpn'):
		print "Failed to initialize pynotify module"
		sys.exit(1)
        
	MPN = Notifier(debug=OPTIONS.debug, notify_timeout=OPTIONS.timeout,
		show_keys=OPTIONS.keys, persist=OPTIONS.persist, once=OPTIONS.once, 
		title_format=OPTIONS.title_format, body_format=OPTIONS.body_format,
		icon=OPTIONS.default_icon)
        
	# fork if necessary
	if OPTIONS.fork and not OPTIONS.debug:
		if os.fork() != 0:
			sys.exit(0)
        
	# run the notifier
	try:
		MPN.run()
		# We only need the main loop when iterating or if keys are enabled
		if OPTIONS.keys or not OPTIONS.once:
			gtk.main()
	except KeyboardInterrupt:
		MPN.close()
		sys.exit(0)

