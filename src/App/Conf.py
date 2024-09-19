import pickle
from pyautogui import size


class Conf:
    """
    The conf class is used to handle fixed and custom variables that define the application
    Fixed configs are typically used for debugging and compatability
    If there is no set of config files then the default will be used and saved
    Otherwise the custom configs will be loaded memory and used
    """

    VERSION = "VERSION PLACEHOLDER"

    WINDOW = {"PLACEHOLDER": "PLACEHOLDER"}

    KEYS = {"PLACEHOLDER": "PLACEHOLDER"}

    DEFAULTS = {"PLACEHOLDER": "PLACEHOLDER"}

    SCREEN_SIZE: tuple = (
        size() if (size()[0] > 1920 and size()[1] > 1080) else (1920, 1080)
    )

    def __init__(self):
        # call this from somewhere else if there is no loadconf
        pass


def loadConf():
    pass


def saveConf():
    pass
