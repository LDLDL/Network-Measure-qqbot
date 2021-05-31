import argparse
from argparse import ArgumentError


class ArgumentParser(argparse.ArgumentParser):
    def exit(self, status=0, message=None):
        if message is None:
            message = ''
        raise argparse.ArgumentError(None, message)

    def print_help(self, file=None):
        pass

    def print_usage(self, file=None):
        pass
