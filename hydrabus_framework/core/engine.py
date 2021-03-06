import inspect
import pkgutil
import sys

from importlib import import_module
from pathlib import Path
from prompt_toolkit.completion.nested import NestedCompleter
from prompt_toolkit.shortcuts import PromptSession
from prompt_toolkit.styles import Style

from hydrabus_framework.core.config import load_config
from hydrabus_framework.core.Dispatcher import Dispatcher
from hydrabus_framework.modules.AModule import AModule
from hydrabus_framework.utils.logger import Logger


__author__ = "Jordan Ovrè <ghecko78@gmail.com>"


class HydraFramework:
    """
    Framework core engine
    """
    def __init__(self):
        self.logger = Logger()
        self.app_path = sys.path[0]
        self.current_module = None
        self.current_module_name = None
        self.dispatcher = Dispatcher()
        self.modules = self._list_modules()
        self.modules_history = []
        self.config = load_config()
        self.completer_nested_dict = self._get_dict_completion()
        self.console_completer = NestedCompleter.from_nested_dict(self.completer_nested_dict)
        self.global_options = {}
        self.prompt_style = Style.from_dict({
            # User input (default text), no value = system default.
            '': self.config['THEME']['user_input'],

            # Prompt.
            'base': self.config['THEME']['base'],
            'pound': self.config['THEME']['pound'],
            'module': self.config['THEME']['module'],
            'category': self.config['THEME']['category'],
        })
        self.prompt = [
            ('class:base', '[hbf] '),
            ('class:module', ''),
            ('class:category', ''),
            ('class:pound', '> '),
        ]

    def update_prompt(self):
        """
        Update the user prompt.
        """
        if self.current_module_name is not None:
            category = self.current_module_name.split("/")[0]
            module = self.current_module_name.split("/")[1]
            self.prompt = [
                ('class:base', '[hbf] '),
                ('class:category', '{}'.format(category)),
                ('class:module', '({})'.format(module)),
                ('class:pound', '> '),
            ]
        else:
            self.prompt = [
                ('class:base', '[hbf] '),
                ('class:category', ''),
                ('class:module', ''),
                ('class:pound', '> '),
            ]

    def _get_dict_completion(self):
        """
        Get all command with associated arguments and return a dict for NestedCompleter.
        nested_dict = {
            'set': {
                'hydrabus': None,
                ...
            },
            'setc': {
                {
                    'section1': {
                        {key1: None},
                        {key2: None}
                    }
                }
            'exit': None
            'use': {
                {'module1': None},
                ...
            }
        }
        :return: nested dictionary
        """
        nested_completion_dict = {}
        modules_dict = {}
        config_dict = {}
        # Get all based command
        for command in self.dispatcher.commands:
            if len(command["arguments"]) == 0:
                nested_completion_dict.update({command["name"]: None})
            else:
                nested_completion_dict.update({command["name"]: command["arguments"]})
        # Append all loaded module to use command
        for module in self.modules:
            modules_dict.update({module["path"]: None})
        nested_completion_dict["use"] = modules_dict
        # Append all config section and key to setc command
        for section in self.config:
            if section != "DEFAULT":
                config_key_dict = {}
                config_dict.update({section: None})
                if len(self.config[section]) > 0:
                    for key in self.config[section]:
                        config_key_dict.update({key: None})
                    config_dict[section] = config_key_dict
        nested_completion_dict["setc"] = config_dict
        return nested_completion_dict

    def update_completer_options_list(self):
        """
        Update prompt completer options list when loading a new module.
        :return: Nothing
        """
        options = {}
        if isinstance(self.current_module, AModule):
            for option in self.current_module.options:
                options.update({option["Name"]: None})
        self.completer_nested_dict["set"] = options
        self.completer_nested_dict["unset"] = options
        self.console_completer = NestedCompleter.from_nested_dict(self.completer_nested_dict)

    def update_completer_global_options_list(self):
        """
        Update prompt completer global options list when loading a new module.
        :return: Nothing
        """
        options = {}
        for keys, _ in self.global_options.items():
            options.update({keys: None})
        self.completer_nested_dict["setg"] = options
        self.completer_nested_dict["unsetg"] = options
        self.console_completer = NestedCompleter.from_nested_dict(self.completer_nested_dict)

    def _list_modules(self):
        """
        Generate modules path and attributes list.
        :return: List of available modules
        """
        modules = []
        module_name = "hbfmodules"

        try:
            package = import_module(module_name)
        except ImportError:
            self.logger.handle("Unable to find any modules, please run 'hbfupdate' "
                               "script to install available modules...", Logger.ERROR)
        else:
            for loader, module, is_pkg in pkgutil.walk_packages(package.__path__, prefix=package.__name__ + '.'):
                try:
                    imported_module = import_module(module)
                    for x in dir(imported_module):
                        obj = getattr(imported_module, x)
                        if inspect.isclass(obj) and issubclass(obj, AModule) and obj is not AModule:
                            module_path = module.replace('hbfmodules.', '').replace('.', '/')
                            modules.append({"path": module_path, "class": obj})
                except ImportError:
                    self.logger.handle('Error dynamically import package "{}"...'.format(module), Logger.ERROR)
        self.logger.handle("{} modules loaded, run 'hbfupdate' command to install the latest modules"
                           .format(len(modules)), Logger.USER_INTERACT)
        return modules

    def run(self, file_script=None):
        """
        Main loop, waiting for user input.
        :return:
        """
        session = PromptSession()
        # This parts is used to automate test by passing file script
        if file_script is not None:
            file_script = Path(file_script)
            if file_script.is_file():
                with file_script.open() as f:
                    commands = f.readlines()
                for command in commands:
                    command = session.prompt(self.prompt, style=self.prompt_style, default=command.strip(),
                                             accept_default=True)
                    self.dispatcher.handle(self, command)
                    self.update_prompt()
            else:
                self.logger.handle("File does not exist or it is not a file", self.logger.ERROR)
        # Normal mode waiting for user_input
        while True:
            try:
                command = session.prompt(self.prompt, style=self.prompt_style, completer=self.console_completer,
                                         complete_while_typing=False)
                self.dispatcher.handle(self, command)
                self.update_prompt()
            except KeyboardInterrupt:
                self.logger.handle("Please use 'exit' command or ctrl+D key to properly quit the framework",
                                   Logger.INFO)
            except EOFError:
                exit(0)
