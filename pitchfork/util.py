import os
import yaml
import click


def mkdir_config(obj):
    try:
        os.mkdir(obj.credentials_dir)
    except FileExistsError:
        pass


def write_config(obj):
    mkdir_config(obj)
    data = {
        'email': obj.email,
        'password': obj.password,
        'api_url': obj.api_url
    }
    try:
        with open(obj.credentials_file, 'w') as fh:
            yaml.dump(data, fh, default_flow_style=False)
    except (OSError, IOError, KeyError):
        raise click.FileError(obj.credentials_file)


def read_file_contents(path):
    with open(path) as fh:
        return fh.read().strip()
