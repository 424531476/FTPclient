import configparser


class Config:
    def __init__(self, filename, encoding='utf8'):
        self.__config = configparser.ConfigParser()
        self.__config.read(filename, encoding)

    def __getitem__(self, item):
        if item in self.__config:
            return self.__config[item]
        return dict()
