#!/usr/bin/env python
import sys, threading
import liblo
from gi.repository import Gtk
from gi.repository import Gdk
import re

DEBUG=True

class OSCServer(liblo.ServerThread):
    def __init__(self, app):
        liblo.ServerThread.__init__(self, 9000)
        self.app = app

    def parse_rgb(self, rgbstr):
        return [float(x) for x in re.match("RGB\(([\.0-9]+),([\.0-9]+),([\.0-9]+)\)", rgbstr).groups()]

    @liblo.make_method(None, None)
    def fallback(self, path, args):
        if DEBUG:
            print "received unknown message '%s'" % path
            print args
        chunks = path.split("/")
        if len(chunks) == 4:
            if chunks[1] == 'track' and chunks[3] == 'color':
                track = int(chunks[2])
                for clip in range(1,8+1):
                    color = self.parse_rgb(args[0])
                    self.app.gui.leds[track][clip].color = color
                    self.app.gui.leds[track][clip].queue_draw()

class App(object):
    def __init__(self):
        self.host = "127.0.0.1"
        self.port = 8000

        self.osc_target = liblo.Address(self.port)
        self.gui = Gui(self)

        self.gui.connect("delete-event", Gtk.main_quit)
        self.gui.connect('destroy', lambda quit: Gtk.main_quit())

    def run(self):
        try:
            server = OSCServer(self)
        except ServerError, err:
            print str(err)
            sys.exit()

        server.start()
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
        #color = Gdk.color_parse('#234fdb')
        #self.modify_bg(Gtk.StateType.PRELIGHT, color)
        #self.set_double_buffered()

    def pressed(self, tgt, ev):
        if ev.touch.type == Gdk.EventType.TOUCH_BEGIN:
            liblo.send(self.osc, self.msg)

class ColorOSCButton(Gtk.Widget):
    __gtype_name__ = 'ColorOSCButton'

    def __init__(self, label, osc_target, msg):
        Gtk.Widget.__init__(self)
        self.osc = osc_target
        self.msg = msg
        self.connect("touch-event", self.pressed)
        self.color = (0.95, 0.95, 0.95)
        self.set_size_request(40, 40)

    def pressed(self, tgt, ev):
        if ev.touch.type == Gdk.EventType.TOUCH_BEGIN:
            liblo.send(self.osc, self.msg)

    def do_draw(self, cr):
        # paint background
        cr.set_source_rgb(*list(self.color))
        #cr.paint()
        allocation = self.get_allocation()
        cr.rectangle(0, 0, allocation.width, allocation.height)
        cr.fill()

    def do_realize(self):
        allocation = self.get_allocation()
        attr = Gdk.WindowAttr()
        attr.window_type = Gdk.WindowType.CHILD
        attr.x = allocation.x
        attr.y = allocation.y
        attr.width = allocation.width
        attr.height = allocation.height
        attr.visual = self.get_visual()
        attr.event_mask = self.get_events() | Gdk.EventMask.EXPOSURE_MASK | Gdk.EventMask.TOUCH_MASK
        WAT = Gdk.WindowAttributesType
        mask = WAT.X | WAT.Y | WAT.VISUAL

        window = Gdk.Window(self.get_parent_window(), attr, mask);
        self.set_window(window)
        self.register_window(window)

        self.set_realized(True)
        window.set_background_pattern(None)


class Gui(Gtk.Window):
    def __init__(self, app):
        Gtk.Window.__init__(self, title="OSC Launchpad")
        self.app = app

        #gobject.threads_init()

        self.table = Gtk.Table(8, 8, True)
        self.add(self.table)
        self.leds = [[False for x in range(8+1)] for x in range(8+1)] 

        for track in range(1,8+1):
            for clip in range(1,8+1):
                self.leds[track][clip] = ColorOSCButton(
                    "%i:%i" % (track, clip),
                    self.app.osc_target,
                    liblo.Message("/track/%i/clip/%i/launch" % (track, clip))
                )
                self.table.attach(
                    self.leds[track][clip],
                    track-1,track,
                    clip-1,clip,
                    Gtk.AttachOptions.EXPAND,
                    Gtk.AttachOptions.EXPAND,
                    10,
                    10
                )

        self.show_all()

    def quit(self):
        Gtk.main_quit()

if __name__=='__main__':
    app = App()
    app.run()



