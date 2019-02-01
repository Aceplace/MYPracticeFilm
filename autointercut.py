import sys

import os
import shutil
import subprocess

from autointercututils import *

BLANK_MOVIE_PATH = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), 'blank.mp4')

class VideoClipGroup:
    def __init__(self, directory, base_synchronize_index=0, base_offset=0):
        self.directory = directory
        self.clips = []

        self.clips = get_movie_file_paths(directory)
        self.clips = with_datetime(self.clips)
        self.clips = with_duration(self.clips)
        self.clips = with_synchronized_time(self.clips, self.clips[base_synchronize_index]['datetime'], base_offset)
        self.clips.sort(key=lambda movie_file: movie_file['synchronize_time'])


def get_synchronized_grouping(base_clip_group, secondary_clip_group):
    base_clips = base_clip_group.clips
    secondary_clips = secondary_clip_group.clips
    matched_clip_pairs = []
    i = 0
    j = 0
    while i < len(base_clips) or j < len(secondary_clips):
        if not i < len(base_clips):
            matched_clip_pairs.append((None, secondary_clips[j]['file_path']))
            j += 1
            continue
        if not j < len(secondary_clips):
            matched_clip_pairs.append((base_clips[i]['file_path'], None))
            i += 1
            continue
        if do_times_overlap(base_clips[i], secondary_clips[j]):
            matched_clip_pairs.append((base_clips[i]['file_path'], secondary_clips[j]['file_path']))
            i += 1
            j += 1
        elif base_clips[i]['synchronize_time'] < secondary_clips[j]['synchronize_time']:
            matched_clip_pairs.append((base_clips[i]['file_path'], None))
            i += 1
        else:
            matched_clip_pairs.append((None, secondary_clips[j]['file_path']))
            j += 1
    return matched_clip_pairs


def get_sync_name(index, extension):
    index += 1
    if index < 10:
        return f'aic000{index}{extension}'
    elif index < 100:
        return f'aic00{index}{extension}'
    elif index < 1000:
        return f'aic0{index}{extension}'
    else:
        return f'aic{index}{extension}'


def auto_sync_cut_folders(base_directory, base_synchronize_index, base_offset,
                          secondary_directory, secondary_synchronize_index, secondary_offset, option='RENAME_AND_PAD'):

    base_clip_group = VideoClipGroup(base_directory, base_synchronize_index, base_offset)
    secondary_clip_group = VideoClipGroup(secondary_directory, secondary_synchronize_index, secondary_offset)
    matched_clip_pairs = get_synchronized_grouping(base_clip_group, secondary_clip_group)

    if option == 'RENAME_AND_PAD':
        output_dir = ''
    else:
        output_dir = 'output'
        if not os.path.exists(os.path.join(base_directory, 'output')):
            os.makedirs(os.path.join(base_directory, 'output'))
        if not os.path.exists(os.path.join(secondary_directory, 'output')):
            os.makedirs(os.path.join(secondary_directory, 'output'))

    for i, matched_clip_pair in enumerate(matched_clip_pairs):
        if matched_clip_pair[0]:
            _, extension = os.path.splitext(matched_clip_pair[0])
            if option == 'RENAME_AND_PAD':
                os.rename(matched_clip_pair[0], os.path.join(os.path.dirname(matched_clip_pair[0]), get_sync_name(i, extension)))
            else:
                shutil.copyfile(matched_clip_pair[0], os.path.join(base_directory, output_dir, get_sync_name(i, extension)))
        else:
            shutil.copyfile(BLANK_MOVIE_PATH, os.path.join(base_directory, output_dir, get_sync_name(i, '.mp4')))
        if matched_clip_pair[1]:
            _, extension = os.path.splitext(matched_clip_pair[1])
            if option == 'RENAME_AND_PAD':
                os.rename(matched_clip_pair[1], os.path.join(os.path.dirname(matched_clip_pair[1]), get_sync_name(i, extension)))
            else:
                shutil.copyfile(matched_clip_pair[1], os.path.join(secondary_directory, output_dir, get_sync_name(i, extension)))
        else:
            shutil.copyfile(BLANK_MOVIE_PATH, os.path.join(secondary_directory, output_dir, get_sync_name(i, '.mp4')))


def auto_cut_secondary(base_directory, base_synchronize_index, base_offset,
                        secondary_directory, secondary_synchronize_index, secondary_offset):

    base_clip_group = VideoClipGroup(base_directory, base_synchronize_index, base_offset)
    secondary_clip_group = VideoClipGroup(secondary_directory, secondary_synchronize_index, secondary_offset)

    base_clips = base_clip_group.clips
    secondary_clips = secondary_clip_group.clips

    if not os.path.exists(os.path.join(secondary_directory, 'output')):
        os.makedirs(os.path.join(secondary_directory, 'output'))

    j = 0
    sm_st = secondary_clips[j]['synchronize_time']
    sm_path = secondary_clips[j]['file_path']
    for i, base_clip in enumerate(base_clips):
        bm_st = base_clip['synchronize_time']
        bm_duration = base_clip['duration']

        while bm_st > sm_st + secondary_clips[j]['duration']:
            j += 1
            if j < len(secondary_clips):
                sm_st = secondary_clips[j]['synchronize_time']
                sm_path = secondary_clips[j]['file_path']
            else:
                break

        if not j < len(secondary_clips) or bm_st + bm_duration < sm_st:
            shutil.copyfile(BLANK_MOVIE_PATH, os.path.join(os.path.join(secondary_directory, 'output', get_sync_name(i, '.mp4'))))
        elif bm_st < sm_st and bm_st + bm_duration > sm_st:
            subclip_duration = to_ffmpeg_duration(bm_st + bm_duration - sm_st + 1)
            subclip_name = os.path.join(secondary_directory, 'output', get_sync_name(i, os.path.splitext(sm_path)[1]))
            sub_proc = subprocess.Popen(['ffmpeg', '-y', '-ss', '00:00:00', '-i', sm_path, '-c', 'copy', '-t', subclip_duration, subclip_name])
            sub_proc.wait()
        else:
            subclip_duration = to_ffmpeg_duration(bm_duration + 2)
            subclip_start_time = to_ffmpeg_duration(bm_st - sm_st - 1) if bm_st - sm_st - 1 > 0 else to_ffmpeg_duration(bm_st - sm_st)
            subclip_name = os.path.join(secondary_directory, 'output', get_sync_name(i, os.path.splitext(sm_path)[1]))
            sub_proc = subprocess.Popen(['ffmpeg', '-y', '-ss', subclip_start_time, '-i', sm_path, '-c', 'copy', '-t', subclip_duration, subclip_name])
            sub_proc.wait()


if __name__ == '__main__':
    # Parameter should be baseDirectory baseSynchronizeIndex baseOffset
    # secondaryDirectory secondarySynchronizeIndex secondaryOffset option
    try:
        base_directory = sys.argv[1]
        base_sync_index = int(sys.argv[2])
        base_offset = int(sys.argv[3])

        secondary_directory = sys.argv[4]
        secondary_sync_index = int(sys.argv[5])
        secondary_offset = int(sys.argv[6])

        option = sys.argv[7]

        if option.upper() == 'SYNC_CUT_DIRS':
            auto_sync_cut_folders(base_directory, base_sync_index, base_offset,
                                  secondary_directory, secondary_sync_index, secondary_offset)
        elif option.upper() == 'AUTO_CUT_SEC':
            auto_cut_secondary(base_directory, base_sync_index, base_offset,
                                    secondary_directory, secondary_sync_index, secondary_offset)
        else:
            print('No proper option given for auto sync', file=sys.stderr)


    except IndexError:
        print('Incorrect arguments passed to autointercut.', file=sys.stderr)















