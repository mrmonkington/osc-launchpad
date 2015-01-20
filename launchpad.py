#!/usr/bin/env python
import sys, threading
import liblo
from gi.repository import Gtk
from gi.repository import Gdk

class App(object):
    def __init__(self):
        self.host = "127.0.0.1"
        self.port = 8000

        self.osc_target = liblo.Address(self.port)
        self.gui = Gui(self)

        self.gui.connect("delete-event", Gtk.main_quit)
        self.gui.connect('destroy', lambda quit: Gtk.main_quit())

    def run(self):
        Gtk.main()

    def quit(self, *arg):
        self.gui.quit()

    def event(self, key, val):
        for ev in self.events:
            if key == ev.key:
                #self.gui.log(ev.path, val)
                ev.val = val
                ev.send()

class OSCButton(Gtk.Button):
    def __init__(self, label, osc_target, msg):
        Gtk.Button.__init__(self, label)
        self.osc = osc_target
        self.msg = msg
        self.connect("touch-event", self.pressed)
        #self.set_double_buffered()

    def pressed(self, tgt, ev):
        if ev.touch.type == Gdk.EventType.TOUCH_BEGIN:
            liblo.send(self.osc, self.msg)

class Gui(Gtk.Window):
    def __init__(self, app):
        Gtk.Window.__init__(self, title="OSC Launchpad")
        self.app = app

        #gobject.threads_init()

        self.table = Gtk.Table(8, 8, True)
        self.add(self.table)

        for track in range(1,8+1):
            for clip in range(1,8+1):
                self.table.attach_defaults(
                    OSCButton(
                        "%i:%i" % (track, clip),
                        self.app.osc_target,
                        liblo.Message("/track/%i/clip/%i/launch" % (track, clip))
                    ),
                    track-1,track,
                    clip-1,clip
                )

        self.show_all()

    def quit(self):
        Gtk.main_quit()

if __name__=='__main__':
    app = App()
    app.run()
