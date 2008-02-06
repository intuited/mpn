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
# Simply launch ./mpn.py


"""Simple libnotify notifier for mpd"""

import os, sys, cgi
from optparse import OptionParser

import gobject
import gtk
import mpdclient2
import pynotify

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
    refresh_time = 500 # in ms
    notify_timeout = 0 # in ms
    host = ""
    mpd = None
    status = None
    current = None
    iterate_handler = None

    def get_host(self):
        """get host name from MPD_HOST env variable"""
        host = os.environ.get('MPD_HOST', 'localhost')
        if '@' in host:
            return host.split('@', 1)
        return host

    def get_time(self):
        """Get current time and total lentght of the current song"""
        time = self.status.time
        now, length = [int(c) for c in time.split(':')]
        now_time = convert_time(now)
        length_time = convert_time(length)

        if self.debug:
            print "Position : " + now_time + " / " + length_time
        return (now_time, length_time)

    def get_title(self):
        """Get the current song title"""
        try:
            title = self.current.title
        except AttributeError:
            title = "????"
            print "<Pas de titre trouvé>"
        if self.debug:
            print "Titre : " + title
        return title

    def get_album(self):
        """Get the current song album"""
        try:
            album = self.current.album
        except AttributeError:
            album = "????"
            print "<Pas d'album trouvé>"
        if self.debug:
            print "Album : " + album
        return album

    def get_artist(self):
        """Get the current song artist"""
        try:
            artist = self.current.artist
        except AttributeError:
            artist = "????"
            print "<Pas d'artiste trouvé>"
        if self.debug:
            print "Artiste : " + artist
        return artist

    def notify(self):
        """Display the notification"""
        self.status = self.mpd.status()

        # only if there is a song currently playing
        if not self.status.state in ['play', 'pause']:
            if self.debug:
                print "Pas de lecture en cours sur le serveur " + self.host
            return True

        # only if the song has changed
        new_current = self.mpd.currentsong()
        if self.current == new_current:
            return True
        self.current = new_current

        # get values and make the strings html safe
        album = cgi.escape(self.get_album())
        title = cgi.escape(self.get_title())
        artist = cgi.escape(self.get_artist())
        _, length = self.get_time()

        if self.debug:
            print ""

        body = "de <b>" + artist + "</b> in <i>" + album + \
               "</i>\nDurée : " + length

        # set paramaters and display the notice
        notif = pynotify.Notification(title, body)
        notif.set_timeout(self.notify_timeout)
        if not notif.show():
            print "<Impossible d'afficher la notification>"
            return False

        return True

    def run(self):
        """Launch the iteration"""
        self.iterate_handler = gobject.timeout_add(self.refresh_time,
                                                   self.notify)

    def __init__(self, debug=False, notify_timeout=3):
        """Initialisation of mpd client and pynotify"""
        self.debug = debug
        # param notify_timeout is in seconds
        self.notify_timeout = 1000 * notify_timeout
        self.host = self.get_host()

        try:
            self.mpd = mpdclient2.connect()
        except mpdclient2.socket.error:
            print "Impossible de se connecter au serveur " + self.host
            sys.exit(1)

        pynotify.init('mpn')

if __name__ == "__main__":
    # initializate the argument parser
    PARSER = OptionParser()

    # debug mode
    PARSER.set_defaults(debug=False)
    PARSER.add_option("--debug", action="store_true", dest="debug")

    # does mpn will fork ?
    PARSER.add_option("--nodaemon", action="store_false", dest="fork")
    PARSER.add_option("-d", "--daemon", action="store_true", dest="fork")
    PARSER.set_defaults(fork=True)

    # how many time the notice will be shown
    PARSER.set_defaults(timeout=3)
    PARSER.add_option("-t", "--timeout", type="int", action="store", dest="timeout")

    # parse the commandline
    (OPTIONS, ARGS) = PARSER.parse_args()

    # initializate the notifier
    MPN = Notifier(debug=OPTIONS.debug, notify_timeout=OPTIONS.timeout)

    # fork if necessary
    if OPTIONS.fork and not OPTIONS.debug:
        if os.fork() != 0:
            sys.exit(0)

    # run the notifier
    MPN.run()
    gtk.main()
