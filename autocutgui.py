import json
import os
import re
import subprocess
import tkinter as tk
import TkinterDnD2 as tkdnd
from autointercut import VideoClipGroup, auto_sync_cut_folders, auto_cut_secondary
from PIL import Image, ImageTk



class ClipGroupFrame(tk.Frame):
    def __init__(self, root, clip_label):
        tk.Frame.__init__(self, root)
        self.clip_info = None
        self.selected_index = None
        self.seek_time = 0

        # Clip listbox
        tk.Label(self, text=f'{clip_label} Clips').grid(row=0, column=0)

        clip_name_lb_frame = tk.Frame(self)
        clip_name_lb_frame.grid(row=1, column=0, sticky='NS')
        clip_name_lb_frame.grid_rowconfigure(0, weight=1)

        y_scroll = tk.Scrollbar(clip_name_lb_frame, orient=tk.VERTICAL)
        y_scroll.grid(row=0, column=1, sticky='NS')
        x_scroll = tk.Scrollbar(clip_name_lb_frame, orient=tk.HORIZONTAL)
        x_scroll.grid(row=1, column=0, sticky='WE')

        self.clip_name_lb = tk.Listbox(clip_name_lb_frame, xscrollcommand=x_scroll.set, yscrollcommand=y_scroll.set,
                                       exportselection=False)
        self.clip_name_lb.bind('<<ListboxSelect>>', self.select_clip)
        self.clip_name_lb.grid(row=0, column=0, sticky='NS')
        self.clip_name_lb.bind('<FocusIn>', lambda event: self.focus_set())
        x_scroll.config(command=self.clip_name_lb.xview)
        y_scroll.config(command=self.clip_name_lb.yview)

        clip_name_lb_frame.drop_target_register(tkdnd.DND_FILES)
        clip_name_lb_frame.dnd_bind('<<Drop>>', self.populate_listbox_items)

        # Clip panel
        self.clip_panel = tk.Label(self)
        self.clip_panel.grid(row=2, column=0)
        self.clip_panel.bind('<Button-1>', lambda event: self.focus_set())
        self.bind('<KeyPress>', self.seek)


    def populate_listbox_items(self, event):
        self.clip_info = None
        self.selected_index = None
        directory = event.data
        match = re.fullmatch('{.*}', event.data)
        if match:
            directory = event.data[1:-1]
        if not os.path.isdir(directory):
            raise ValueError('Clip Source must be Directory')

        self.video_clip_group = VideoClipGroup(directory, 0, 0)

        self.clip_name_lb.delete(0, tk.END)
        for clip in self.video_clip_group.clips:
            clip_name = os.path.basename(clip['file_path'])
            self.clip_name_lb.insert(tk.END, clip_name)


    def select_clip(self, event):
        self.seek_time = 0
        self.selected_index = self.clip_name_lb.index(tk.ANCHOR)
        self.current_clip_path = os.path.join(self.video_clip_group.directory, self.clip_name_lb.get(self.selected_index))

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
        timestamp = to_ffmpeg_duration(self.seek_time)
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

    def seek(self, event):
        if not self.clip_info:
            return
        if event.keysym == 'Left':
            next_seek_time = self.seek_time - 1
        elif event.keysym == 'Right':
            next_seek_time = self.seek_time + 1
        elif event.keysym == 'Up':
            next_seek_time = self.seek_time - 5
        elif event.keysym == 'Down':
            next_seek_time = self.seek_time + 5
        else:
            return

        if next_seek_time >= 0 and next_seek_time < self.clip_info['duration']:
            self.seek_time = next_seek_time
            self.update_clip_panel()


class AutocutGui(tk.Frame):
    def __init__(self, root):
        tk.Frame.__init__(self, root)

        self.primary_clips_frame = ClipGroupFrame(self, 'Primary')
        self.primary_clips_frame.grid(row=0, column=0)
        self.secondary_clips_frame = ClipGroupFrame(self, 'Secondary')
        self.secondary_clips_frame.grid(row=0, column=1)

        # Buttons to perform autocuts
        match_and_rename_btn = tk.Button(self, text='Match and Rename',
                                        command=lambda : self.match('RENAME_AND_PAD'))
        match_and_rename_btn.grid(row=2, column=0, columnspan=2, sticky='WE')
        match_and_copy_btn = tk.Button(self, text='Match and Copy',
                                       command=lambda : self.match('COPY'))
        match_and_copy_btn.grid(row=3, column=0, columnspan=2, sticky='WE')
        autocut_secondary_from_primary_btn = tk.Button(self, text='Autocut Secondary from Primary',
                                                       command=self.autocut_secondary_from_primary)
        autocut_secondary_from_primary_btn.grid(row=4, column=0, columnspan=2, sticky='WE')

    def match(self, option):
        primary_clip_group = self.primary_clips_frame.video_clip_group
        primary_selected_index = self.primary_clips_frame.selected_index
        primary_seek_time = self.primary_clips_frame.seek_time
        secondary_selected_index = self.secondary_clips_frame.selected_index
        secondary_clip_group = self.secondary_clips_frame.video_clip_group
        secondary_seek_time = self.secondary_clips_frame.seek_time
        if primary_clip_group == None or primary_selected_index == None \
            or secondary_clip_group == None or secondary_clip_group == None:
            return

        auto_sync_cut_folders(primary_clip_group.directory, primary_selected_index, primary_seek_time,
                              secondary_clip_group.directory, secondary_selected_index, secondary_seek_time,
                              option)


    def autocut_secondary_from_primary(self):
        primary_clip_group = self.primary_clips_frame.video_clip_group
        primary_selected_index = self.primary_clips_frame.selected_index
        primary_seek_time = self.primary_clips_frame.seek_time
        secondary_selected_index = self.secondary_clips_frame.selected_index
        secondary_clip_group = self.secondary_clips_frame.video_clip_group
        secondary_seek_time = self.secondary_clips_frame.seek_time
        if primary_clip_group == None or primary_selected_index == None \
                or secondary_clip_group == None or secondary_clip_group == None:
            return

        auto_cut_secondary(primary_clip_group.directory, primary_selected_index, primary_seek_time,
                              secondary_clip_group.directory, secondary_selected_index, secondary_seek_time,)


if __name__ == '__main__':
    root = tkdnd.TkinterDnD.Tk()
    cut_gui = AutocutGui(root)
    cut_gui.pack()
    root.mainloop()