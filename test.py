import exiftool
import copy
from dateutil import parser, relativedelta
import os


supported_extensions = ['.MTS']


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
            'duration': get_tag_value('Duration', metadata)
        }
        for metadata in metadata_batch
    ]


def with_synchronized_time(synchronize_datetime, offset, movie_files):
    movie_files = copy.deepcopy(movie_files)
    for movie_file in movie_files:
        rd = to_seconds(relativedelta.relativedelta(movie_file['datetime'], synchronize_datetime))
        movie_file['synchronize_time'] = rd - offset
    return movie_files


base_directory = r"C:\Users\AcePl\Desktop\Wide"
secondary_directory = r"C:\Users\AcePl\Desktop\Tight"

with exiftool.ExifTool() as et:
    metadata_batch = et.get_tags_batch(['DateTimeOriginal', 'Duration'], get_movie_file_from_directory(base_directory))
    base_movie_files = parse_exif_batch(metadata_batch)
    metadata_batch = et.get_tags_batch(['DateTimeOriginal', 'Duration'], get_movie_file_from_directory(secondary_directory))
    secondary_movie_files = parse_exif_batch(metadata_batch)


base_movie_files = with_synchronized_time(base_movie_files[0]['datetime'], 10, base_movie_files)
base_movie_files.sort(key=lambda movie_file: movie_file['synchronize_time'])

secondary_movie_files = with_synchronized_time(secondary_movie_files[0]['datetime'], 0, secondary_movie_files)
secondary_movie_files.sort(key=lambda movie_file: movie_file['synchronize_time'])

for movie_file in base_movie_files:
    print(movie_file)

for movie_file in secondary_movie_files:
    print(movie_file)










