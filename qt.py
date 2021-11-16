#!/usr/bin/env python3
"""
Script to monitor and tweak stuff in qbittorrent.

It reannounces torrents with no tracker registered.

It checks incomplete torrents against the free disk
space and pauses torrents to ensure the disk space
will not be filled up.

It can optionally autoresume paused torrents if disk
space is available.
"""

import argparse
import logging
import shutil
import time
import json
import re
import qbittorrentapi

SECONDS_IN_DAY = 60 * 60 * 24

DEFAULTS = {
    'config': '/opt/qtpy/config.json',
    'autoresume': False
}

def load_params(config_file):
    "load params from file"
    with open(config_file) as file:
        params = json.load(file)

    return params


def sizeof_fmt(num, suffix='B'):
    """convert number of bytes into human abbreviated form"""
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


def free_space(directory):
    """get free space on download area"""
    _, _, free = shutil.disk_usage(directory)
    return free


def pause(torrent, qbt_client):
    """pause torrent"""
    logging.info('pause - %s: %s', torrent.hash[-6:], {torrent.name})
    qbt_client.torrents_pause(torrent_hashes=torrent.hash)


def resume(torrent, qbt_client):
    """resume torrent"""
    logging.info('resume - %s: %s', torrent.hash[-6:], {torrent.name})
    qbt_client.torrents_resume(torrent_hashes=torrent.hash)
    # Also reannounce just to make sure
    logging.info('reannounce - %s: %s', torrent.hash[-6:], {torrent.name})
    qbt_client.torrents_reannounce(torrent_hashes=torrent.hash)


def contains(string, regex):
    """check if a string contains a regex"""
    return re.compile(regex).search(string)


def days(torrent):
    """return age of torrent in days"""
    return (time.time() - torrent.completion_on) / SECONDS_IN_DAY


def check_all_incomplete(incomplete, qbt_client, params):
    """check incomplete aren't going to blow free space"""
    total_active = 0
    total_paused = 0
    paused = []
    active = []
    for inc in incomplete:
        # logging.info('incomplete %d %s (%s) %s',
        #              inc.completion_on, inc.state, sizeof_fmt(inc.amount_left), {inc.name})
        if inc.state == 'pausedDL':
            # Add an extra check as we don't want to unpause completed
            # torrents
            if inc.completion_on <= 0:
                total_paused = total_paused + inc.amount_left
                paused.append(inc)
        else:
            total_active = total_active + inc.amount_left
            active.append(inc)


    # Get free space and adjust for the min free space (GB)
    free = free_space(params["download_dir"])
    free = free - (params["min_free_gb"] * 1024 * 1024 * 1024)

    # Optionally autoresume torrents if there is space available
    if params["autoresume"]:
        # If the total of incomplete torrents is less than free space
        # then we can resume them all happily
        total_left = total_paused + total_active
        if total_left < free:
            # unpause everything
            for torrent in paused:
                resume(torrent, qbt_client)
                total_paused = total_paused = torrent.amount_left
                total_active = total_active + torrent.amount.left
            return

        # Otherwise do a piecemeal check to see if we can resume
        # any currently paused torrents
        if total_active < free:
            # Check to see if we can resume anything paused, starting
            # with the torrents with the least remaining
            for torrent in sorted(paused, key=lambda k: k['amount_left']):
                if (total_active + torrent.amount_left) < free:
                    resume(torrent, qbt_client)
                    total_active = total_active + torrent.amount_left
                    total_paused = total_paused - torrent.amount_left
            return

    # Finally we have more active than free so must pause some
    # Start with the ones with the most remaining
    for torrent in sorted(active, key=lambda k: k['amount_left'], reverse=True):
        pause(torrent, qbt_client)
        total_active = total_active - torrent.amount_left
        total_paused = total_paused + torrent.amount_left

        # We only need to pause enough to get under free space
        if total_active < free:
            break


def do_work(params):
    """Everything happens here!"""

    # instantiate a Client using the appropriate WebUI configuration
    qbt_client = qbittorrentapi.Client(host=params["qbit"]["host"],
                                       username=params["qbit"]["user"],
                                       password=params["qbit"]["password"])

    # the Client will automatically acquire/maintain a logged in state in line with
    # any request. Therefore, this is not necessary; however, you many want to test
    # the provided login credentials.
    try:
        qbt_client.auth_log_in()
    except qbittorrentapi.LoginFailed as ex:
        logging.error(ex)
        raise ex

    # Gather information on the torrents. We manage tagging,
    # re-announce and identifying incomplete torrents here.
    count = 0
    paused = 0
    incomplete = []
    amount_left = 0
    for torrent in qbt_client.torrents_info():
        # counters
        count = count + 1

        # Check for incomplete torrents
        # The double check here is in case a completed torrent has lost
        # its progress. We don't want to manually interfere with that!
        if torrent.progress != 1.0 and torrent.completion_on <= 0:
            incomplete.append(torrent)
            amount_left = amount_left + torrent.amount_left

        # Count pause torrents but perform no extra checks on them
        # Specifically we don't want to try and reannounce paused torrents!
        if 'paused' in torrent.state:
            paused = paused + 1
            continue

        # Some other states to ignore
        if 'checking' in torrent.state:
            logging.info('skipping %s - %s: %s [%s %.2f]',
                         torrent.category, torrent.hash[-6:], {torrent.name}, torrent.state,
                         torrent.progress)
            continue

        # If there is no tracker then try re-announcing...
        if not torrent.tracker or len(torrent.tracker) == 0:
            logging.info('reannounce %s - %s: %s [%s]',
                         torrent.category, torrent.hash[-6:], {torrent.name}, torrent.state)
            qbt_client.torrents_reannounce(torrent_hashes=torrent.hash)
            continue

    # Check incomplete torrents aren't going to blow disk space
    check_all_incomplete(incomplete, qbt_client, params)


def main():
    """Setup logging and make things happen"""
    parser = argparse.ArgumentParser(description='Manage Qbittorrent')
    parser.add_argument('--config', default=DEFAULTS['config'])
    parser.add_argument('--auto-resume', dest='autoresume', action='store_true')
    parser.add_argument('--no-auto-resume', dest='autoresume', action='store_false')
    parser.set_defaults(autoresume=False)
    args = parser.parse_args()

    # load the config file
    params = load_params(args.config)

    # make sure some values are present
    if not 'autoresume' in params.values():
        params['autoresume'] = args.autoresume

    logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s',
                        level=logging.INFO,
                        filename=params["log_file"])
    logging.debug('startup')

    do_work(params)

    logging.debug('shutdown')


if __name__ == '__main__':
    main()
