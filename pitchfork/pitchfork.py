import click
import yaml
import os
import requests
import logging
from jinja2 import Template


__version__ = "0.0.1"


class LogMaker():
    def __init__(self, output_format, name, level):
        self.logger = logging.getLogger(name)
        self.logger_ch = logging.StreamHandler()
        self.formatter = logging.Formatter(output_format)
        self.logger_ch.setFormatter(self.formatter)
        self.logger.addHandler(self.logger_ch)
        self.logger.setLevel(level)

LOG = {
    'CRITICAL': logging.CRITICAL,  # 50
    'ERROR':    logging.ERROR,     # 40
    'WARNING':  logging.WARNING,   # 30  # python default level
    'INFO':     logging.INFO,      # 20
    'DEBUG':    logging.DEBUG      # 10
}


DEBUG_FORMAT = (
    "%(levelname)-5s %(lineno)4s %(filename)-18s:%(funcName)-13s"
    ": %(message)s"
)

QUIET_FORMAT = "%(message)s"

logger_quiet = LogMaker(
    output_format=QUIET_FORMAT,
    name="logging_quiet",
    level=LOG['INFO']
)


def eprint(*args,  **kwargs):
    level = kwargs.pop('level', LOG['INFO'])
    if level == LOG['DEBUG']:
        logger_quiet.logger.debug(*args, **kwargs)
    elif level == LOG['INFO']:
        logger_quiet.logger.info(*args, **kwargs)
    elif level >= LOG['WARNING']:
        logger_quiet.logger.warning(*args, **kwargs)


class Config(object):

    def __init__(self, **kwargs):
        self.api = kwargs.get('api')

    @property
    def api(self):
        return self.__api

    @api.setter
    def api(self, api):
        self.__api = api

    @property
    def data(self):
        credentials_file = os.path.join(
            os.getenv('HOME'),
            '.pitchforkrc'
        )
        try:
            with open(credentials_file) as fh:
                file_contents = yaml.load(fh.read())
                return file_contents
        except (OSError, IOError, KeyError):
            raise click.FileError(credentials_file)

    @property
    def api_key(self):
        return self.data['credentials'].pop('api_key')

    @property
    def username(self):
        return self.data['credentials'].pop('username')

    @property
    def url(self):
        return self.data.pop('url')

    def __repr__(self):
        return (
            '<Credentials {0}, {1}, {2}>'.
            format(self. url, self.username, self.api_key)
        )


class Api(requests.Session):

    def __init__(self, username, api_key, **kwargs):
        self.api_key = api_key
        self.username = username
        super().__init__(**kwargs)
        self.params.update({'api_key': self.api_key})

    def __repr__(self):
        return '<Api {0}, {1}>'.format(self.username, self.api_key)


class Address:

    def __init__(self, address, reports_url):
        self.address = address
        self.reports_url = reports_url

    @property
    def address(self):
        return self.__address

    @address.setter
    def address(self, address):
        self.__address = address

    @property
    def reports_url(self):
        return self.__reports_url

    @reports_url.setter
    def reports_url(self, reports_url):
        self.__reports_url = reports_url

    def __repr__(self):
        return (
            '<Address {0}, {1}>'.
            format(self.address, self.reports_url)
        )


def set_verbose(ctx, param, verbose=False):
    if verbose:
        logger_quiet.logger.setLevel(LOG['DEBUG'])
        logger_quiet.logger_ch.setFormatter(
            logging.Formatter(DEBUG_FORMAT)
        )
    else:
        logger_quiet.logger.setLevel(LOG['INFO'])


@click.group()
@click.option(
    '--verbose',
    is_flag=True,
    callback=set_verbose,
    expose_value=False
)
@click.pass_context
def pitchfork(ctx):
    ctx.obj = Config()
    ctx.obj.api = Api(ctx.obj.username, ctx.obj.api_key)


@pitchfork.group(chain=True)
@click.pass_context
def report(ctx, **kwargs):
    pass


@report.command('get')
@click.pass_context
@click.option('--address', required=True)
def report_get(ctx, address):
    resp = ctx.obj.api.get(
        '{0}/report'.format(ctx.obj.url),
        params=ctx.obj.api.params.update({'address': address})
    )
    if resp.status_code != 200:
        raise click.ClickException(resp.json()['messages'])
    report = resp.json()
    if not bool(report):
        raise click.ClickException("No port probe found.")
    report_template = Template("""
======
Report
======

Address:        {{ address }}
Date:           {{ date_started }}
{% if not portprotocols -%}
No Opened Ports.
{% else -%}
Opened Ports:   {%- for pp, data in portprotocols.items() -%}
                {% set product = data.product or data.port.name -%}
                {% set version = data.version or 'Not found' %}
                - {{ pp }}:
                    - product: {{ product }}
                    - version: {{ version }}
                {% endfor %}
{% endif %}

""")

    eprint(
        report_template.render(
            address=address,
            date_started=report['time']['started'],
            portprotocols=report['ports']
        )
    )


@pitchfork.group(chain=True)
@click.option('--debug', required=False)
@click.pass_context
def address(ctx, **kwargs):
    ctx.obj.debug = kwargs.get('debug')


@address.command('get')
@click.pass_context
@click.option('--address', required=True)
def address_get(ctx, address):
    resp = ctx.obj.api.get(
        '{0}/address'.format(ctx.obj.url),
        params=ctx.obj.api.params.update({'address': address})
    )
    if resp.status_code != 200:
        raise click.ClickException(resp.json()['messages'])
    eprint(resp.json(), level=LOG['DEBUG'])
    address = Address(**resp.json())
    eprint(address.address)


@address.command('list')
@click.pass_context
def address_list(ctx):
    resp = ctx.obj.api.get('{0}/address'.format(ctx.obj.url))
    if resp.status_code != 200:
        raise click.ClickException(resp.json()['messages'])
    for address in resp.json():
        eprint(address['address'])


@address.command('add')
@click.pass_context
@click.option('--address', required=True)
def address_add(ctx, address):
    resp = ctx.obj.api.post(
        ctx.obj.url,
        params=ctx.obj.api.params.update({'address': address})
    )
    if not resp.ok:
        raise click.ClickException(resp.json()['messages'])
    eprint(resp.json(), level=LOG['DEBUG'])
    address = Address(**resp.json())
    eprint("Address added.")


@address.command('portprobe')
@click.pass_context
@click.option('--address', required=True)
def address_portprobe(ctx, address):
    resp = ctx.obj.api.get(
        '{0}/portprobe'.format(ctx.obj.url),
        params=ctx.obj.api.params.update({'address': address})
    )
    if resp.status_code != 200:
        raise click.ClickException(resp.json()['messages'])
    eprint("Port probing address.")


if __name__ == '__main__':
    pitchfork()
