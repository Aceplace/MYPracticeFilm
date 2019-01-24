import sys

import exiftool
import copy
from dateutil import parser, relativedelta
import os
import shutil
import subprocess

supported_extensions = ['.MTS']
blank_movie_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), 'blank.mp4')


def get_tag_value(tag, metadata):
    for full_tag, value in metadata.items():
        if tag in full_tag:
            return value
    raise ValueError(f'{tag} not within metadata tags.')


def to_seconds(relative_delta):
    return relative_delta.seconds + relative_delta.minutes * 60 + relative_delta.hours * 3600


def get_movie_file_from_directory(directory):
    return [f'{os.path.join(directory, filename)}{file_extension}'
            for filename, file_extension in [os.path.splitext(item_path) for item_path in os.listdir(directory)]
            if file_extension.upper() in supported_extensions]


def parse_exif_batch(metadata_batch):
    return [
        {
            'file_path': get_tag_value('SourceFile', metadata),
            'datetime': parser.parse(get_tag_value('DateTimeOriginal', metadata)),
        }
        for metadata in metadata_batch
    ]

def with_duration(movie_files):
    movie_files = copy.deepcopy(movie_files)
    for movie_file in movie_files:
        cmd = ['ffprobe', '-i', movie_file['file_path'], '-show_entries', 'format=duration', '-v', 'quiet', '-of', 'csv=%s' % ("p=0")]
        duration = subprocess.check_output(cmd)
        duration = float(duration)
        movie_file['duration'] = duration
    return movie_files

def with_synchronized_time(synchronize_datetime, offset, movie_files):
    movie_files = copy.deepcopy(movie_files)
    for movie_file in movie_files:
        rd = to_seconds(relativedelta.relativedelta(movie_file['datetime'], synchronize_datetime))
        movie_file['synchronize_time'] = rd - offset
    return movie_files


def synchronize_angles(base_movie_files, secondary_movie_files):
    matched_file_groups = []
    i = 0
    j = 0
    while i < len(base_movie_files) or j < len(secondary_movie_files):
        if not i < len(base_movie_files):
            matched_file_groups.append((None, secondary_movie_files[j]['file_path']))
            j += 1
            continue
        if not j < len(secondary_movie_files):
            matched_file_groups.append((base_movie_files[i]['file_path'], None))
            i += 1
            continue
        if times_does_overalp(base_movie_files[i], secondary_movie_files[j]):
            matched_file_groups.append((base_movie_files[i]['file_path'], secondary_movie_files[j]['file_path']))
            i += 1
            j += 1
        elif base_movie_files[i]['synchronize_time'] < secondary_movie_files[j]['synchronize_time']:
            matched_file_groups.append((base_movie_files[i]['file_path'], None))
            i += 1
        else:
            matched_file_groups.append((None, secondary_movie_files[j]['file_path']))
            j += 1
    return matched_file_groups


def times_does_overalp(movie_file_1, movie_file_2):
    if movie_file_1['synchronize_time'] < movie_file_2['synchronize_time']:
        return movie_file_1['synchronize_time'] + movie_file_1['duration'] > movie_file_2['synchronize_time']
    else:
        return movie_file_2['synchronize_time'] + movie_file_2['duration'] > movie_file_1['synchronize_time']


def rename_and_pad(matched_file_groups, base_directory, secondary_directory):
    for i, matched_file_group in enumerate(matched_file_groups):
        print(i, matched_file_group)
        if matched_file_group[0]:
            _, extension = os.path.splitext(matched_file_group[0])
            os.rename(matched_file_group[0], os.path.join(os.path.dirname(matched_file_group[0]), get_sync_name(i, extension)))
        else:
            shutil.copyfile(blank_movie_path, os.path.join(os.path.join(base_directory, get_sync_name(i, '.mp4'))))
        if matched_file_group[1]:
            _, extension = os.path.splitext(matched_file_group[1])
            os.rename(matched_file_group[1], os.path.join(os.path.dirname(matched_file_group[1]), get_sync_name(i, extension)))
        else:
            shutil.copyfile(blank_movie_path, os.path.join(os.path.join(secondary_directory, get_sync_name(i, '.mp4'))))


def get_sync_name(index, extension):
    index += 1
    if index < 10:
        return f'000{index}{extension}'
    elif index < 100:
        return f'00{index}{extension}'
    elif index < 1000:
        return f'0{index}{extension}'
    else:
        return f'{index}{extension}'


def synchronize_folders(base_directory, base_synchronize_index, base_offset,
                        secondary_directory, secondary_synchronize_index, seconadry_offset):

    base_movie_file_paths = get_movie_file_from_directory(base_directory)
    secondary_movie_file_paths = get_movie_file_from_directory(secondary_directory)
    with exiftool.ExifTool() as et:
        metadata_batch = et.get_tags_batch(['DateTimeOriginal'], base_movie_file_paths)
        base_movie_files = parse_exif_batch(metadata_batch)
        metadata_batch = et.get_tags_batch(['DateTimeOriginal'], secondary_movie_file_paths)
        secondary_movie_files = parse_exif_batch(metadata_batch)

    base_movie_files = with_duration(base_movie_files)
    base_movie_files = with_synchronized_time(base_movie_files[base_synchronize_index]['datetime'],
                                              base_offset, base_movie_files)
    base_movie_files.sort(key=lambda movie_file: movie_file['synchronize_time'])
    for movie in base_movie_files:
        print(movie)

    secondary_movie_files = with_duration(secondary_movie_files)
    secondary_movie_files = with_synchronized_time(secondary_movie_files[secondary_synchronize_index]['datetime'],
                                                   seconadry_offset, secondary_movie_files)
    secondary_movie_files.sort(key=lambda movie_file: movie_file['synchronize_time'])
    for movie in secondary_movie_files:
        print(movie)

    matched_file_groups = synchronize_angles(base_movie_files, secondary_movie_files)
    rename_and_pad(matched_file_groups, base_directory, secondary_directory)


if __name__ == '__main__':
    # Parameter should be baseDirectory baseSynchronizeIndex baseOffset secondaryDirectory secondarySynchronizeIndex secondaryOffset
    try:
        base_directory = sys.argv[1]
        base_sync_index = sys.argv[2]
        base_offset = sys.argv[3]

        secondary_directory = sys.argv[4]
        secondary_sync_index = sys.argv[5]
        secondary_offset = sys.argv[6]
    except IndexError:
        synchronize_folders(r"C:\Users\AcePl\Desktop\Wide", 0, 10, r"C:\Users\AcePl\Desktop\Tight", 0, 0)















