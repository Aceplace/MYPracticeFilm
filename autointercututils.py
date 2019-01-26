import copy
import os
import subprocess


from dateutil import parser, relativedelta
import exiftool


SUPPORTED_EXTENSIONS = ['.MTS', '.MP4']
DATETIME_TAGS = ['DateTimeOriginal', 'CreateDate']


def to_seconds(relative_delta):
    return relative_delta.seconds + relative_delta.minutes * 60 + relative_delta.hours * 3600


def get_movie_file_paths(directory):
    return [{'file_path': f'{os.path.join(directory, filename)}{file_extension}'}
            for filename, file_extension in [os.path.splitext(item_path) for item_path in os.listdir(directory)]
            if file_extension.upper() in SUPPORTED_EXTENSIONS]


def with_datetime(movie_files):
    movie_files = copy.deepcopy(movie_files)

    with exiftool.ExifTool() as et:
        for movie_file in movie_files:
            metadata = et.get_tags(DATETIME_TAGS, movie_file['file_path'])

            for tag in DATETIME_TAGS:
                datetime = None
                for full_tag, value in metadata.items():
                    if tag in full_tag:
                        datetime = value
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


def with_synchronized_time(movie_files, synchronize_datetime, offset):
    movie_files = copy.deepcopy(movie_files)
    for movie_file in movie_files:
        rd = to_seconds(relativedelta.relativedelta(movie_file['datetime'], synchronize_datetime))
        movie_file['synchronize_time'] = rd - offset
    return movie_files


def do_times_overlap(movie_file_1, movie_file_2):
    if movie_file_1['synchronize_time'] < movie_file_2['synchronize_time']:
        return movie_file_1['synchronize_time'] + movie_file_1['duration'] > movie_file_2['synchronize_time']
    else:
        return movie_file_2['synchronize_time'] + movie_file_2['duration'] > movie_file_1['synchronize_time']


def to_ffmpeg_duration(duration):
    hours = int(duration // 3600)
    minutes = int((duration - (hours * 3600)) // 60)
    seconds = duration % 60
    return f'{hours}:{minutes}:{seconds}'