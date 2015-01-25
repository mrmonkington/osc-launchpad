#!/usr/bin/env python
import sys, threading
import liblo
from gi.repository import Gtk
from gi.repository import GObject
from gi.repository import Gdk
import cairo
import re
import colorsys

DEBUG=True

def bpm_to_ms(bpm):
    return int(60*1000/bpm)

beat = bpm_to_ms(120)
num_scenes = 8
num_tracks = 12

def lighten_rgb(col, mul):
    mul = float(mul)
    hls = list(colorsys.rgb_to_hls(*col))
    hls[1] = hls[1] + ((1.0 - hls[1]) / mul) * (mul-1)
    return colorsys.hls_to_rgb(*hls)

class OSCServer(liblo.ServerThread):
    def __init__(self, app):
        liblo.ServerThread.__init__(self, 9000)
        self.app = app

        self.osc_routes = {
            "/play" : self.set_playing,
            "/track/([0-9]+)/color" : self.set_track_color,
            "/track/([0-9]+)/clip/([0-9]+)/isQueued" : self.set_clip_queued,
            "/track/([0-9]+)/clip/([0-9]+)/isPlaying" : self.set_clip_playing,
            "/track/([0-9]+)/clip/([0-9]+)/name" : self.set_clip_name,
            "/track/([0-9]+)/clip/([0-9]+)/hasContent" : self.set_clip_has_content
        }

    def parse_rgb(self, rgbstr):
        return [float(x) for x in re.match("RGB\(([\.0-9]+),([\.0-9]+),([\.0-9]+)\)", rgbstr).groups()]


    @liblo.make_method(None, None)
    def handle(self, path, args):
        if DEBUG:
            print "received '%s'" % path
            print args
        for pattern, action in self.osc_routes.items():
            match = re.match(pattern, path)
            if match:
                path_args = list(match.groups())
                path_args.append(args)
                action(*path_args)
                break

    def set_playing(self, args):
        pass
    
    def set_track_color(self, track, args):
        track = int(track)
        for clip in range(1,num_scenes+1):
            color = self.parse_rgb(args[0])
            self.app.gui.leds[track][clip].color = color
            self.app.gui.leds[track][clip].queue_draw()

    def set_clip_queued(self, track, clip, args):
        track = int(track)
        clip = int(clip)
        self.app.gui.leds[track][clip].is_queued = bool(args[0])
        self.app.gui.leds[track][clip].queue_draw()

    def set_clip_playing(self, track, clip, args):
        track = int(track)
        clip = int(clip)
        self.app.gui.leds[track][clip].is_playing = bool(args[0])
        self.app.gui.leds[track][clip].queue_draw()

    def set_clip_name(self, track, clip, args):
        track = int(track)
        clip = int(clip)
        self.app.gui.leds[track][clip].label_content = args[0]
        self.app.gui.leds[track][clip].queue_draw()

    def set_clip_has_content(self, track, clip, args):
        track = int(track)
        clip = int(clip)
        self.app.gui.leds[track][clip].has_content = bool(args[0])
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
        except liblo.ServerError, err:
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

class OSCButton(Gtk.Widget):

    def __init__(self, osc_target, msg):
        Gtk.Widget.__init__(self)
        self.osc = osc_target
        self.msg = msg
        #self.connect("touch-event", self.touched)
        self.connect("button-press-event", self.clicked)
        self.color = (0.95, 0.95, 0.95)
        self.set_size_request(80, 60)

    def touched(self, tgt, ev):
        # a sort of debounce, cos touch fires loads of events
        if ev.touch.type == Gdk.EventType.TOUCH_BEGIN:
            liblo.send(self.osc, self.msg)

    def clicked(self, tgt, ev):
        liblo.send(self.osc, self.msg)

    def do_draw(self, cr):
        color = (0.95, 0.95, 0.95)
        cr.set_source_rgb(*color)

        allocation = self.get_allocation()
        cr.rectangle(0, 0, allocation.width, allocation.height)
        cr.fill()
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.rectangle(0, 0, allocation.width, allocation.height)
        cr.stroke()

    def do_realize(self):
        allocation = self.get_allocation()
        attr = Gdk.WindowAttr()
        attr.window_type = Gdk.WindowType.CHILD
        attr.x = allocation.x
        attr.y = allocation.y
        attr.width = allocation.width
        attr.height = allocation.height
        attr.visual = self.get_visual()
        attr.event_mask = self.get_events() | Gdk.EventMask.EXPOSURE_MASK | Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.TOUCH_MASK
        WAT = Gdk.WindowAttributesType
        mask = WAT.X | WAT.Y | WAT.VISUAL

        window = Gdk.Window(self.get_parent_window(), attr, mask);
        self.set_window(window)
        self.register_window(window)

        self.set_realized(True)
        window.set_background_pattern(None)

    def play_icon(self, cr):
        allocation = self.get_allocation()
        cr.move_to(allocation.width-16, 6)
        cr.line_to(allocation.width-6, 11)
        cr.line_to(allocation.width-16, 16)
        cr.close_path()
        cr.set_source_rgb(0.7, 0.7, 0.7)
        cr.fill()

class ClipButton(OSCButton):

    def __init__(self, track, clip, osc_target, msg):
        OSCButton.__init__(self, osc_target, msg)
        self.color = (0.95, 0.95, 0.95)
        self.has_content = False
        self.is_playing = False
        self.is_queued = False
        self.flash_state = True

        self.timeout_id = GObject.timeout_add(beat, self.on_timeout)

        self.label_index = u"%i:%i" % (track, clip)
        self.label_content = ""

    def on_timeout(self):
        if self.flash_state:
            self.flash_state = False
        else:
            self.flash_state = True
        self.queue_draw()
        # timeouts must return True or will not trigger again
        return True

    def do_draw(self, cr):
        # paint background
        color = lighten_rgb(self.color, 1.4)
        if self.has_content:
            if self.is_playing:
                if self.flash_state:
                    color = self.color
            elif self.is_queued:
                color = lighten_rgb(self.color, 1.2)
        else:
            color = (0.95, 0.95, 0.95)

        cr.set_source_rgb(*color)

        allocation = self.get_allocation()
        cr.rectangle(0, 0, allocation.width, allocation.height)
        cr.fill()
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.rectangle(0, 0, allocation.width, allocation.height)
        cr.stroke()

        cr.set_source_rgb(0.3, 0.3, 0.3)
        cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL, 
            cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(11)
        cr.move_to(4,15)
        cr.show_text(self.label_index)
        cr.move_to(4,30)
        cr.show_text(self.label_content)

        self.play_icon(cr)


class StopButton(OSCButton):

    def __init__(self, osc_target, msg):
        OSCButton.__init__(self, osc_target, msg)

    def do_draw(self, cr):
        allocation = self.get_allocation()
        cr.set_source_rgb(0.95, 0.95, 0.95)
        cr.rectangle(0, 0, allocation.width, allocation.height)
        cr.fill()
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.rectangle(0, 0, allocation.width, allocation.height)
        cr.stroke()

        cr.set_source_rgb(0.6, 0.6, 0.6)
        cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL, 
            cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(11)
        cr.move_to(4,15)
        cr.text_path("Stop")
        cr.fill()

        # stop icon
        cr.rectangle(allocation.width-16, 6, 10, 10)
        cr.set_source_rgb(0.7, 0.7, 0.7)
        cr.fill()

class SceneButton(OSCButton):

    def __init__(self, scene, osc_target, msg):
        OSCButton.__init__(self, osc_target, msg)
        self.scene = scene

    def do_draw(self, cr):
        allocation = self.get_allocation()
        cr.set_source_rgb(0.95, 0.95, 0.95)
        cr.rectangle(0, 0, allocation.width, allocation.height)
        cr.fill()
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.rectangle(0, 0, allocation.width, allocation.height)
        cr.stroke()

        cr.set_source_rgb(0.6, 0.6, 0.6)
        cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL, 
            cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(11)
        cr.move_to(4,15)
        cr.text_path("Scene %i" % self.scene)
        cr.fill()

        self.play_icon(cr)

class Gui(Gtk.Window):
    def __init__(self, app):
        Gtk.Window.__init__(self, title="OSC Launchpad")
        self.app = app

        #gobject.threads_init()

        self.table = Gtk.Table(num_scenes+2, num_tracks+1, True)
        self.add(self.table)
        self.leds = [[False for x in range(num_scenes+1)] for x in range(num_tracks+1)] 
        self.headers = [False for x in range(num_tracks+1)] 

        for header in range(1, num_tracks+1):
            self.headers[header] = Gtk.Label('Track %i' % header)
            self.table.attach(
                self.headers[header],
                header,header+1,
                0,1,
                Gtk.AttachOptions.EXPAND | Gtk.AttachOptions.FILL,
                Gtk.AttachOptions.EXPAND | Gtk.AttachOptions.FILL,
                2,
                2
            )

        for track in range(1,num_tracks+1):
            for clip in range(1,num_scenes+1):
                self.leds[track][clip] = ClipButton(
                    track,
                    clip,
                    self.app.osc_target,
                    liblo.Message("/track/%i/clip/%i/launch" % (track, clip))
                )
                self.table.attach(
                    self.leds[track][clip],
                    track,track+1,
                    clip,clip+1,
                    Gtk.AttachOptions.EXPAND | Gtk.AttachOptions.FILL,
                    Gtk.AttachOptions.EXPAND | Gtk.AttachOptions.FILL,
                    2,
                    2
                )

        for track in range(1, num_tracks+1):
            self.table.attach(
                StopButton(
                    self.app.osc_target,
                    liblo.Message("/track/%i/clip/stop" % (track,))
                ),
                track,track+1,
                num_scenes+1,num_scenes+2,
                Gtk.AttachOptions.EXPAND | Gtk.AttachOptions.FILL,
                Gtk.AttachOptions.EXPAND | Gtk.AttachOptions.FILL,
                2,
                2
            )

        for scene in range(1, num_scenes+1):
            self.table.attach(
                SceneButton(
                    scene,
                    self.app.osc_target,
                    liblo.Message("/scene/%i/launch" % (scene,))
                ),
                0,1,
                scene,scene+1,
                Gtk.AttachOptions.EXPAND | Gtk.AttachOptions.FILL,
                Gtk.AttachOptions.EXPAND | Gtk.AttachOptions.FILL,
                2,
                2
            )

        self.table.attach(
            StopButton(
                self.app.osc_target,
                liblo.Message("/stop")
            ),
            0,1,
            num_scenes+1,num_scenes+2,
            Gtk.AttachOptions.EXPAND | Gtk.AttachOptions.FILL,
            Gtk.AttachOptions.EXPAND | Gtk.AttachOptions.FILL,
            2,
            2
        )

        self.show_all()

    def quit(self):
        Gtk.main_quit()

if __name__=='__main__':
    app = App()
    app.run()



