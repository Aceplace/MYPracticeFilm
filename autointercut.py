import sys

import exiftool
import copy
from dateutil import parser, relativedelta
import os
import shutil
import subprocess

SUPPORTED_EXTENSIONS = ['.MTS', '.MP4']
DATETIME_TAGS = ['DateTimeOriginal', 'CreateDate', 'FileCreateDate']
BLANK_MOVIE_PATH = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), 'blank.mp4')


def get_tag_value(tag, metadata):
    for full_tag, value in metadata.items():
        if tag in full_tag:
            return value
    return None


def to_seconds(relative_delta):
    return relative_delta.seconds + relative_delta.minutes * 60 + relative_delta.hours * 3600


def get_movie_file_from_directory(directory):
    return [{'file_path': f'{os.path.join(directory, filename)}{file_extension}'}
            for filename, file_extension in [os.path.splitext(item_path) for item_path in os.listdir(directory)]
            if file_extension.upper() in SUPPORTED_EXTENSIONS]


def with_datetime(movie_files):
    movie_files = copy.deepcopy(movie_files)

    with exiftool.ExifTool() as et:
        for movie_file in movie_files:
            metadata = et.get_tags(DATETIME_TAGS, movie_file['file_path'])

            for tag in DATETIME_TAGS:
                datetime = get_tag_value(tag, metadata)
                if datetime != None:
                    break

            if datetime == None:
                raise ValueError('Couldn\'t get a datetime for {movie_file["file_path"]}')

            movie_file['datetime'] = parser.parse(datetime)
    return movie_files


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
            shutil.copyfile(BLANK_MOVIE_PATH, os.path.join(os.path.join(base_directory, get_sync_name(i, '.mp4'))))
        if matched_file_group[1]:
            _, extension = os.path.splitext(matched_file_group[1])
            os.rename(matched_file_group[1], os.path.join(os.path.dirname(matched_file_group[1]), get_sync_name(i, extension)))
        else:
            shutil.copyfile(BLANK_MOVIE_PATH, os.path.join(os.path.join(secondary_directory, get_sync_name(i, '.mp4'))))


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


def movie_from_directories(base_directory, base_synchronize_index, base_offset,
                        secondary_directory, secondary_synchronize_index, secondary_offset):
    base_movie_files = get_movie_file_from_directory(base_directory)
    secondary_movie_files = get_movie_file_from_directory(secondary_directory)

    base_movie_files = with_datetime(base_movie_files)
    secondary_movie_files = with_datetime(secondary_movie_files)

    base_movie_files = with_duration(base_movie_files)
    base_movie_files = with_synchronized_time(base_movie_files[base_synchronize_index]['datetime'],
                                              base_offset, base_movie_files)
    base_movie_files.sort(key=lambda movie_file: movie_file['synchronize_time'])
    for movie in base_movie_files:
        print(movie)

    secondary_movie_files = with_duration(secondary_movie_files)
    secondary_movie_files = with_synchronized_time(secondary_movie_files[secondary_synchronize_index]['datetime'],
                                                   secondary_offset, secondary_movie_files)
    secondary_movie_files.sort(key=lambda movie_file: movie_file['synchronize_time'])
    for movie in secondary_movie_files:
        print(movie)

    return base_movie_files, secondary_movie_files

def synchronize_cut_folders(base_directory, base_synchronize_index, base_offset,
                        secondary_directory, secondary_synchronize_index, secondary_offset):
    base_movie_files, secondary_movie_files = movie_from_directories(base_directory, base_synchronize_index, base_offset,
                                                            secondary_directory, secondary_synchronize_index, secondary_offset)
    matched_file_groups = synchronize_angles(base_movie_files, secondary_movie_files)
    rename_and_pad(matched_file_groups, base_directory, secondary_directory)

def auto_cut_secondary(base_directory, base_synchronize_index, base_offset,
                        secondary_directory, secondary_synchronize_index, secondary_offset):
    base_movie_files, secondary_movie_files = movie_from_directories(base_directory, base_synchronize_index, base_offset,
                                                            secondary_directory, secondary_synchronize_index, secondary_offset)
    print('now auto_cut')


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
            synchronize_cut_folders(base_directory, base_sync_index, base_offset,
                                    secondary_directory, secondary_sync_index, secondary_offset)
        elif option.upper() == 'AUTO_CUT_SEC':
            auto_cut_secondary(base_directory, base_sync_index, base_offset,
                                    secondary_directory, secondary_sync_index, secondary_offset)
        else:
            print('No proper option given for auto sync', file=sys.stderr)


    except IndexError:
        print('Incorrect arguments passed to autointercut.', file=sys.stderr)















