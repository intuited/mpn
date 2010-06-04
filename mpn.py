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

format_title = "%t"
format_body = "<b>%b</b><br><i>%a</i><br>(%d)"

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

class Notifier:
	"Main class for mpn"
	debug = False
	keys = False
	persist = False
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
		except KeyError:
			try:
				title = self.current["file"]
			except KeyError:
				title = "???"
		if self.debug:
			print "Titre : " + title
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
		except KeyError:
			data = ""
		if self.debug:
			print tag + ": " + album
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
        
	def press_prev(notification=None, action=None, data=None):
		if self.debug:
			print "Previous song"
		self.mpd.previous()
        
	def press_next():
		if self.debug:
			print "Next song"
		self.mpd.next()
        
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
			title = self.re_t.sub(self.get_title(True), title)
			title = self.re_f.sub(self.get_file(True), title)
			title = self.re_d.sub(self.get_time(), title)
			title = self.re_a.sub(self.get_tag('artist', True), title)
			title = self.re_b.sub(self.get_tag('album', True), title)
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
		# Ugly, but there's no mpd.isconnected() method
			self.disconnect()
			if self.persist:
				self.connect()
				return True
			else:
				print "Lost connection to server, exiting..."
				sys.exit(1)
                
		# set paramaters and display the notice
		if self.debug:
			print "Title string: " + title
			print "Body string: " + body
		self.notifier.update(title, body)
		if self.keys:
			self.notifier.add_action("clicked", "&lt;&lt;", self.press_prev, None)
			self.notifier.add_action("clicked", ">>", self.press_next, None)
		if not self.notifier.show():
			print "Impossible to display the notification"
			return False

		return True
        
	def run(self):
		"""Launch the iteration"""
		self.iterate_handler = gobject.timeout_add(self.refresh_time, self.notify)
        
	def close(self):
		return self.disconnect()
        
	def __init__(self, debug=False, notify_timeout=3, show_keys=False,
		persist=False, title_format=None, body_format=None):
		"""Initialisation of mpd client and pynotify"""
		self.debug = debug
		self.keys = show_keys
		self.persist = persist
		self.notifier = pynotify.Notification("Song title", "Song details")
		# param notify_timeout is in seconds
		if notify_timeout == 0:
			self.notifier.set_timeout(pynotify.EXPIRES_NEVER)
		else:
			self.notifier.set_timeout(1000 * notify_timeout)
                
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
                
		pynotify.init('mpn')

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
        
	# whether to print updates on all song changes
	PARSER.add_option("-k", "--keys", action="store_true", dest="keys",
	# If only there were better documentation on how to use libnotify's buttons
#		default=False, help="Add Prev/Next buttons to notify window")
		default=False, help=SUPPRESS_HELP)
        
	# whether to print updates on all song changes
	PARSER.add_option("-o", "--once", action="store_false", dest="repeat",
		default=True, help="Notify once and exit")
        
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
	MPN = Notifier(debug=OPTIONS.debug, notify_timeout=OPTIONS.timeout,
		show_keys=OPTIONS.keys, persist=OPTIONS.persist,
		title_format=OPTIONS.title_format, body_format=OPTIONS.body_format)
        
	# fork if necessary
	if OPTIONS.fork and not OPTIONS.debug:
		if os.fork() != 0:
			sys.exit(0)
        
	# run the notifier
	if OPTIONS.repeat:
		try:
			MPN.run()
			gtk.main()
		except KeyboardInterrupt:
			MPN.close()
			sys.exit(0)
	else:
		MPN.notify()

