import os
import logging
import time
from collections import deque

import digitalocean
from dotenv import load_dotenv, find_dotenv

from main import app
from models import APIKey, Job
import util

load_dotenv(find_dotenv())

JUDGE_URL = os.getenv('JUDGE_URL', '')
MAX_JURIES = 10

DIGITALOCEAN_API_TOKEN = os.getenv('DIGITALOCEAN_API_TOKEN', '')

# TODO: Add stop command for jury systemd service
USER_DATA_TEMPLATE = '''#!/bin/bash

cat > /etc/systemd/system/docker-jury.service <<EOF
[Unit]
Description=Jury container
Requires=docker.service
After=docker.service

[Service]
Restart=always
ExecStart=/usr/bin/docker run --cap-add=SYS_PTRACE -e JUDGE_URL={judge_url} -e JUDGE_API_KEY={api_key} easyctf/openctf-jury:latest
ExecStop=:

[Install]
WantedBy=default.target
EOF

systemctl daemon-reload
systemctl enable docker-jury
systemctl start docker-jury
'''

logging.getLogger().setLevel(logging.INFO)
logger = logging.getLogger('autoscale')
logger.setLevel(logging.DEBUG)
logging.info('Starting up!')


class Cloud:
    def get_current_jury_count(self):
        raise NotImplemented

    def create_jury(self, n=1):
        raise NotImplemented

    def destroy_jury(self, n=1):
        raise NotImplemented


class DigitalOcean(Cloud):
    def __init__(self, token):
        self.token = token
        self.manager = digitalocean.Manager(token=self.token)

    def _get_juries(self):
        return self.manager.get_all_droplets('jury')

    def get_current_jury_count(self):
        return len(self._get_juries())

    def create_jury(self, n=1):
        for _ in range(n):
            name = 'jury-{}'.format(util.generate_hex_string(8))
            with app.app_context():
                api_key = APIKey.new(name=name, perm_jury=True).key

            digitalocean.Droplet(
                token=self.token,
                name=name,
                region='sfo2',
                image='docker-16-04',
                size_slug='2gb',
                tags=['jury'],
                user_data=USER_DATA_TEMPLATE.format(judge_url=JUDGE_URL, api_key=api_key)
            ).create()

    def destroy_jury(self, n=1):
        juries = self._get_juries()
        n = min(n, len(juries))
        for _ in range(n):
            juries.pop().destroy()
        return n


class LoadIndex:
    def __init__(self, jury_count=1):
        self.window_size = 10
        self.last_n = deque()
        self.jury_count = jury_count

    def update(self, new_load):
        self.last_n.append(new_load)
        if len(self.last_n) > self.window_size:
            self.last_n.popleft()

    def update_jury_count(self, jury_count):
        self.jury_count = jury_count

    def optimal_change(self):
        avg = sum(self.last_n) / len(self.last_n)
        index = avg / self.jury_count
        logger.info('Average enqueued is {} - {} per jury.'.format(avg, index))
        if index >= 20:
            return int(index) // 20
        if index < 2:
            return -1
        return 0


def get_enqueued_jobs():
    with app.app_context():
        return Job.query_can_claim().count()


cloud = DigitalOcean(token=DIGITALOCEAN_API_TOKEN)

load_index = LoadIndex()

# TODO: better tracking of juries
jury_count = cloud.get_current_jury_count()


def tick():
    global jury_count
    enqueued_jobs = get_enqueued_jobs()
    load_index.update(enqueued_jobs)
    load_index.update_jury_count(jury_count)
    optimal_change = load_index.optimal_change()

    logger.info('{} juries currently exist and optimal change is {}.'.format(jury_count, optimal_change))
    if optimal_change >= 2:
        if jury_count < MAX_JURIES:
            to_create = min(optimal_change, MAX_JURIES - jury_count)
            logger.info('Spinning up {} juries.'.format(to_create))
            cloud.create_jury(to_create)
            jury_count += to_create
        else:
            logger.info('Maximum jury count reached.')
    elif optimal_change <= -1:
        # TODO: clean shutdown of juries or detection of jury's current job
        if jury_count > 1:
            to_destroy = min(-optimal_change, jury_count - 1)
            logger.info('Destroying {} juries.'.format(to_destroy))
            destroyed = cloud.destroy_jury(to_destroy)
            jury_count -= destroyed
            logger.info('Destroyed {} juries.'.format(destroyed))
        else:
            logger.info('Not enough juries to destroy!')


if cloud.get_current_jury_count() == 0:
    logger.info('Spinning up 1 jury because none previously existed.')
    cloud.create_jury()
    jury_count += 1

while True:
    tick()

    time.sleep(5)
