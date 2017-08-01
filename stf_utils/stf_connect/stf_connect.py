# -*- coding: utf-8 -*-

import os
import argparse
import json
import logging
import signal
import sys
import time

from stf_utils.config.config import initialize_config_file
from stf_utils.stf_connect.client import SmartphoneTestingFarmClient, STFDevicesConnector, STFConnectedDevicesWatcher

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(level=getattr(logging, LOG_LEVEL))
log = logging.getLogger(__name__)


def set_log_level(_log_level):
    if _log_level:
        log.debug("Changed log level to {0}".format(_log_level.upper()))
        log.setLevel(_log_level.upper())


def parse_args():
    parser = argparse.ArgumentParser(
        description="Utility for connecting "
                    "devices from STF"
    )
    parser.add_argument(
        "-g", "--groups", help="Device groups defined in spec file to connect"
    )
    parser.add_argument(
        "-l", "--log-level", help="Log level"
    )
    parser.add_argument(
        "-c", "--config", help="Path to config file", default="stf-utils.ini"
    )
    return parser.parse_args()


def run():
    def exit_gracefully(signum, frame):
        log.info("Stopping connect service...")
        try:
            thread_stop(devices_watcher_thread)
            thread_stop(devices_connector_thread)
        except NameError as e:
            log.warning("Poll thread is not defined, skipping... {}".format(e))
        log.debug("Stopping main thread...")
        stf.close_all()
        sys.exit(0)

    def thread_stop(thread):
        thread.stop()
        thread.join()

    args = parse_args()
    config = initialize_config_file(args.config)

    signal.signal(signal.SIGINT, exit_gracefully)
    signal.signal(signal.SIGTERM, exit_gracefully)

    set_log_level(args.log_level)
    log.info("Starting connect service...")

    with open(config.main.get("device_spec")) as f:
        device_spec = json.load(f)

    if args.groups:
        log.info("Working only with specified groups: {0}".format(args.groups))
        specified_groups = args.groups.split(",")
        device_spec = [device_group for device_group in device_spec if device_group.get("group_name") in specified_groups]

    stf = SmartphoneTestingFarmClient(
        host=config.main.get("host"),
        common_api_path="/api/v1",
        oauth_token=config.main.get("oauth_token"),
        device_spec=device_spec,
        devices_file_path=config.main.get("devices_file_path"),
        shutdown_emulator_on_disconnect=config.main.get("shutdown_emulator_on_disconnect")
    )
    devices_connector_thread = STFDevicesConnector(stf)
    devices_watcher_thread = STFConnectedDevicesWatcher(stf)
    devices_watcher_thread.start()
    devices_connector_thread.start()

    while True:
        time.sleep(100)

if __name__ == "__main__":
    run()
