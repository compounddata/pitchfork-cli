import click
import yaml
import os
import requests
import logging
import util
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


class ApiAuth(requests.auth.AuthBase):

    session = requests.Session()
    session.headers = {'Content-Type': 'application/json'}
    token_file = os.path.join(
        os.environ.get('HOME'),
        '.pitchfork',
        'token'
    )

    def __init__(self, api_url, username, password):
        self.api_url = api_url
        self.username = username
        self.password = password
        self.token = None
        try:
            self.token = util.read_file_contents(self.token_file)
        except FileNotFoundError:
            self.token = self.login()
        finally:
            self.session.headers.update(
                {'Authentication-Token': self.token}
            )

    def login(self):
        r = requests.get(
            '{0}/account/login'.format(self.api_url),
            headers=self.session.headers,
            auth=(self.username, self.password)
        )
        r.raise_for_status()
        token = r.json()['token']

        # save token
        with open(self.token_file, 'w') as fh:
            fh.write(token)

        return r.json()['token']

    def __call__(self, r):
        r.headers = self.session.headers
        return r


class Config(object):

    credentials_dir = os.path.join(
        os.getenv('HOME'),
        '.pitchfork'
    )
    credentials_file = os.path.join(
        credentials_dir,
        'config'
    )

    def __init__(self):
        pass

    @property
    def data(self):
        with open(self.credentials_file) as fh:
            file_contents = yaml.load(fh.read())
            return file_contents

    @property
    def email(self):
        try:
            email = self.__email
        except AttributeError:
            email = self.data.pop('email')
        finally:
            return email

    @email.setter
    def email(self, email):
        self.__email = email

    @property
    def password(self):
        try:
            password = self.__password
        except AttributeError:
            password = self.data.pop('password')
        finally:
            return password

    @password.setter
    def password(self, password):
        self.__password = password

    @property
    def api_url(self):
        try:
            api_url = self.__api_url
        except AttributeError:
            try:
                api_url = self.data.get('api_url')
            except FileNotFoundError:
                # ~/.pitchfork/config does not exist so point client to
                # production API url.
                api_url = 'https://api.pitchfork.io'
        finally:
            return api_url

    @api_url.setter
    def api_url(self, api_url):
        self.__api_url = api_url

    @property
    def api_auth(self):
        """ApiAuth object used to authenticate with API."""
        return ApiAuth(self.api_url, self.email, self.password)


class BaseResource(object):
    def __init__(self, messages, reports_url):
        self.reports_url = reports_url
        self.messages = messages


class Address(BaseResource):
    def __init__(self, address, messages=None, reports_url=None):
        super().__init__(messages, reports_url)
        self.address = address


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


@pitchfork.group(chain=True)
@click.pass_context
def account(ctx, **kwargs):
    pass


@account.command('register')
@click.pass_context
@click.option('--email', required=True)
@click.option(
    '--password',
    required=True,
    prompt=True,
    hide_input=True,
    confirmation_prompt=True
)
def account_register(ctx, email, password):
    data = {'email': email, 'password': password}
    resp = requests.post(
        '{0}/account/register'.format(ctx.obj.api_url),
        data=data
    )
    if resp.status_code != 200:
        raise click.ClickException(resp.json()['messages'])

    (ctx.obj.email, ctx.obj.password) = (email, password)
    util.write_config(ctx.obj)

    eprint(resp.json()['messages'])


@pitchfork.group(chain=True)
@click.pass_context
def report(ctx, **kwargs):
    pass


@report.command('get')
@click.pass_context
@click.option('--address', required=True)
def report_get(ctx, address):
    resp = requests.get(
        '{0}/report'.format(ctx.obj.api_url),
        auth=ctx.obj.api_auth,
        params={'address': address}
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
@click.pass_context
def address(ctx, **kwargs):
    pass


@address.command('get')
@click.pass_context
@click.option('--address', required=True)
def address_get(ctx, address):
    resp = requests.get(
        '{0}/address'.format(ctx.obj.api_url),
        auth=ctx.obj.api_auth,
        params={'address': address}
    )
    if resp.status_code != 200:
        raise click.ClickException(resp.json()['messages'])
    eprint(resp.json(), level=LOG['DEBUG'])
    address = Address(**resp.json())
    eprint(address.address)


@address.command('list')
@click.pass_context
def address_list(ctx):
    resp = requests.get(
        '{0}/address'.format(ctx.obj.api_url),
        auth=ctx.obj.api_auth
    )
    if resp.status_code != 200:
        raise click.ClickException(resp.json()['messages'])
    for address in resp.json():
        eprint(address['address'])


@address.command('add')
@click.pass_context
@click.option('--address', required=True)
def address_add(ctx, address):
    resp = requests.post(
        '{0}/address'.format(ctx.obj.api_url),
        auth=ctx.obj.api_auth,
        params={'address': address}
    )
    if not resp.ok:
        raise click.ClickException(resp.json()['messages'])
    eprint(resp.json(), level=LOG['DEBUG'])
    eprint(resp.json()['messages'])


@address.command('portprobe')
@click.pass_context
@click.option('--address', required=True)
def address_portprobe(ctx, address):
    resp = requests.get(
        '{0}/portprobe'.format(ctx.obj.api_url),
        auth=ctx.obj.api_auth,
        params={'address': address}
    )
    eprint(resp.json(), level=LOG['DEBUG'])
    if not resp.ok:
        raise click.ClickException(resp.json()['messages'])
    eprint(resp.json()['messages'])


if __name__ == '__main__':
    pitchfork()
