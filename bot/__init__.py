import os
import logging
import queue
import sys
import time
from typing import Optional, List, Tuple, TYPE_CHECKING
if TYPE_CHECKING:
    from bot.config.models import CronEntryModel

from pydantic.error_wrappers import ValidationError
from crontab import CronTab

from bot import (
    TeamTalk,
    cache,
    commands,
    config,
    connectors,
    logger,
    modules,
    player,
    services,
    sound_devices,
    translator,
    app_vars,
)
from bot.utils import sort_cron_tasks


class Bot:
    def __init__(
        self,
        config_file_name: Optional[str],
        cache_file_name: Optional[str] = None,
        log_file_name: Optional[str] = None,
    ) -> None:
        try:
            self.config_manager = config.ConfigManager(config_file_name)
        except ValidationError as e:
            for error in e.errors():
                print(
                    "Error in config:",
                    ".".join([str(i) for i in error["loc"]]),
                    error["msg"],
                )
            sys.exit(1)
        except PermissionError:
            sys.exit(
                "The configuration file cannot be accessed due to a permission error or is already used by another instance of the bot"
            )
        self.config = self.config_manager.config
        self.translator = translator.Translator(self.config.general.language)
        try:
            if cache_file_name:
                self.cache_manager = cache.CacheManager(cache_file_name)
            else:
                cache_file_name = self.config.general.cache_file_name
                if not os.path.isdir(
                    os.path.join(*os.path.split(cache_file_name)[0:-1])
                ):
                    cache_file_name = os.path.join(
                        self.config_manager.config_dir, cache_file_name
                    )
                self.cache_manager = cache.CacheManager(cache_file_name)
        except PermissionError:
            sys.exit(
                "The cache file cannot be accessed due to a permission error or is already used by another instance of the bot"
            )
        self.cache = self.cache_manager.cache
        self.log_file_name = log_file_name
        self.player = player.Player(self)
        self.periodic_player = player.Player(self)
        self.ttclient = TeamTalk.TeamTalk(self)
        self.tt_player_connector = connectors.TTPlayerConnector(self)
        self.periodic_tt_player_connector = connectors.MinimalTTPlayerConnector(self)
        self.sound_device_manager = sound_devices.SoundDeviceManager(self)
        self.service_manager = services.ServiceManager(self)
        self.module_manager = modules.ModuleManager(self)
        self.command_processor = commands.CommandProcessor(self)
        self.scheduled_command_processor = commands.ScheduledCommandProcessor(self)
        self.cron_patterns: List[Tuple[CronTab, CronEntryModel]] = []

    def initialize(self):
        if self.config.logger.log:
            logger.initialize_logger(self)
        logging.debug("Initializing")
        self.sound_device_manager.initialize()
        self.ttclient.initialize()
        self.player.initialize()
        self.periodic_player.initialize()
        self.service_manager.initialize()
        if self.config.schedule.enabled:
            # parse all cron patterns into CronTab instances and store
            for entry in self.config.schedule.patterns:
                logging.debug(
                    f"Parsing cron pattern '{entry.pattern}' and appending to list"
                )
                e = CronTab(entry.pattern)
                self.cron_patterns.append((e, entry))
        logging.debug("Initialized")

    def run(self):
        logging.debug("Starting")
        counter = 0
        counter_total = int(1 / app_vars.loop_timeout)
        self.player.run()
        self.periodic_player.run()
        self.tt_player_connector.start()
        self.periodic_tt_player_connector.start()
        self.command_processor.run()
        self.scheduled_command_processor.run()
        logging.info("Started")
        self._close = False
        while not self._close:
            if self.config.schedule.enabled and counter == counter_total:
                tasks = sort_cron_tasks(self.cron_patterns)
                for ct, entry in tasks:
                    if ct.next() <= 1:
                        # run the associated command here
                        logging.debug(
                            f"Running command '{entry.command}' for cron pattern '{entry.pattern}"
                     )
                        # call the scheduled command processor with the cron entry from config
                        self.scheduled_command_processor(entry)
            try:
                message = self.ttclient.message_queue.get_nowait()
                logging.info(
                    "New message {text} from {username}".format(
                        text=message.text, username=message.user.username
                    )
                )
                self.command_processor(message)
            except queue.Empty:
                pass
            if counter > counter_total:
                counter = 0
            counter += 1
            time.sleep(app_vars.loop_timeout)

    def close(self) -> None:
        logging.debug("Closing bot")
        self.player.close()
        self.periodic_player.close()
        self.ttclient.close()
        self.tt_player_connector.close()
        self.periodic_tt_player_connector.close()
        self.config_manager.close()
        self.cache_manager.close()
        self._close = True
        logging.info("Bot closed")
