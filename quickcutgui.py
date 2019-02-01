import json
import os
import re
import subprocess
import tkinter as tk
import TkinterDnD2 as tkdnd
import bisect
from autointercut import VideoClipGroup, auto_sync_cut_folders, auto_cut_secondary
from PIL import Image, ImageTk


def to_ffmpeg_duration(duration):
    hours = int(duration // 3600)
    minutes = int((duration - (hours * 3600)) // 60)
    seconds = duration % 60
    return f'{hours}:{minutes}:{seconds}'


def pairs(seq):
    it = iter(seq)
    i = next(it, None)
    j = next(it, None)
    while i != None:
        yield i, j
        i = next(it, None)
        j = next(it, None)


class QuickCutGui(tk.Frame):
    def __init__(self, root):
        tk.Frame.__init__(self, root)
        self.current_seek_time = 0
        self.marks = []
        self.current_clip_path = None
        self.clip_info = None

        # Clip Label
        self.clip_drop_lbl = tk.Label(self, text=f'Drop Clip Here')
        self.clip_drop_lbl.grid(row=0, column=0)

        self.clip_drop_lbl.drop_target_register(tkdnd.DND_FILES)
        self.clip_drop_lbl.dnd_bind('<<Drop>>', self.get_file)

        # Clip panel
        self.clip_panel = tk.Label(self)
        self.clip_panel.grid(row=1, column=0)
        self.clip_panel.bind('<Button-1>', lambda event: self.focus_set())
        self.bind_all('<KeyPress>', self.handle_input)

        # Subclip Listbox
        subclip_lb_frame = tk.Frame(self)
        subclip_lb_frame.grid(row=1, column=1, rowspan=2, sticky='NS')
        subclip_lb_frame.grid_rowconfigure(1, weight=1)

        tk.Label(self, text=f'Subclip Times').grid(row=0, column=1)
        y_scroll = tk.Scrollbar(subclip_lb_frame, orient=tk.VERTICAL)
        y_scroll.grid(row=1, column=1, sticky='NS')
        x_scroll = tk.Scrollbar(subclip_lb_frame, orient=tk.HORIZONTAL)
        x_scroll.grid(row=2, column=0, sticky='WE')

        self.subclip_lb = tk.Listbox(subclip_lb_frame, xscrollcommand=x_scroll.set, yscrollcommand=y_scroll.set,
                                       exportselection=False)
        self.subclip_lb.grid(row=1, column=0, sticky='NS')
        tk.Button(subclip_lb_frame, text='Delete subclip', command=self.delete_subclip).grid(row=3, column=0)
        x_scroll.config(command=self.subclip_lb.xview)
        y_scroll.config(command=self.subclip_lb.yview)


    def get_file(self, event):
        self.current_seek_time = 0
        self.current_clip_path = None
        file_path = event.data
        match = re.fullmatch('{.*}', event.data)
        if match:
            file_path = event.data[1:-1]
        if not os.path.isfile(file_path):
            raise ValueError('Clip Source must be File')

        self.current_clip_path = file_path

        video_size_output = subprocess.check_output(['ffprobe',
                                                     '-v', 'quiet',
                                                     '-print_format', 'json',
                                                     '-show_format',
                                                     '-show_streams',
                                                     self.current_clip_path])

        video_info = json.loads(video_size_output)
        self.clip_info = {}
        self.clip_info['width'] = video_info['streams'][0]['width']
        self.clip_info['height'] = video_info['streams'][0]['height']
        self.clip_info['duration'] = float(video_info['streams'][0]['duration'])
        self.update_clip_panel()


    def update_clip_panel(self):
        # Update image
        timestamp = to_ffmpeg_duration(self.current_seek_time)
        image_data = subprocess.check_output(['ffmpeg',
                                              '-ss', timestamp,
                                              '-i', self.current_clip_path,
                                              '-vframes', '1',
                                              '-f', 'image2pipe',
                                              '-vcodec', 'rawvideo',
                                              '-pix_fmt', 'rgb24',
                                              '-'], bufsize=10 ** 8, stderr=subprocess.DEVNULL)
        image = Image.frombytes('RGB', (self.clip_info['width'], self.clip_info['height']), image_data)
        iwidth, iheight = image.size
        aspect_ratio = iwidth / iheight
        image = image.resize((640, int(640 / aspect_ratio)), Image.ANTIALIAS)
        image = ImageTk.PhotoImage(image)
        self.clip_panel.configure(image=image)
        self.clip_panel.image = image

        # Update label
        self.clip_drop_lbl.configure(text=f'{timestamp} {self.seek_time_status()}')

    def update_subclip_lb(self):
        # Update image
        self.subclip_lb.delete(0, tk.END)
        for i, j in pairs(self.marks):
            if j != None:
                self.subclip_lb.insert(tk.END , f'{to_ffmpeg_duration(i)} to {to_ffmpeg_duration(j)}')
            else:
                self.subclip_lb.insert(tk.END, f'{to_ffmpeg_duration(i)} to ---')

    def handle_input(self, event):
        if not self.clip_info:
            return
        if event.keysym == 'Left':
            next_seek_time = self.current_seek_time - 1
        elif event.keysym == 'Right':
            next_seek_time = self.current_seek_time + 1
        elif event.keysym == 'Up':
            next_seek_time = self.current_seek_time - 5
        elif event.keysym == 'Down':
            next_seek_time = self.current_seek_time + 5
        elif event.keysym == 'space':
            self.make_mark()
            return
        else:
            return

        if next_seek_time >= 0 and next_seek_time < self.clip_info['duration']:
            self.current_seek_time = next_seek_time
            self.update_clip_panel()

    def make_mark(self):
        if self.current_seek_time not in self.marks:
            bisect.insort(self.marks, self.current_seek_time)
        self.update_clip_panel()
        self.update_subclip_lb()

    def delete_subclip(self):
        index = self.subclip_lb.curselection()[0]
        index *= 2
        if index < len(self.marks) - 1:
            del self.marks[index:index+2]
        else:
            del self.marks[index]
        self.update_subclip_lb()

    def seek_time_status(self):
        for i,j in pairs(self.marks):
            if self.current_seek_time == i or self.current_seek_time == j:
                return 'On Subclip Border'
            if self.current_seek_time > i and j != None and self.current_seek_time < j:
                return 'In Subclip'
        return 'Out of Subclip'


if __name__ == '__main__':
    root = tkdnd.TkinterDnD.Tk()
    quick_cut_gui = QuickCutGui(root)
    quick_cut_gui.pack()
    root.mainloop()