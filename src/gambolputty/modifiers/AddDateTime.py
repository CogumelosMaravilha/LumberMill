# -*- coding: utf-8 -*-
import datetime
import BaseThreadedModule
from Decorators import ModuleDocstringParser

@ModuleDocstringParser
class AddDateTime(BaseThreadedModule.BaseThreadedModule):
    """
    Add a field with the current datetime.

    Configuration example:

    - module: AddDateTime
      configuration:
        target_field: 'my_timestamp' # <default: '@timestamp'; type: string; is: optional>
        format: '%Y-%M-%dT%H:%M:%S'  # <default: '%Y-%m-%dT%H:%M:%S'; type: string; is: optional>
      receivers:
        - NextModule
    """

    def handleData(self, data):
        """
        Process the event.

        @param data: dictionary
        @return data: dictionary
        """
        data[self.getConfigurationValue('target_field', data)] = datetime.datetime.utcnow().strftime(self.getConfigurationValue('format', data))
        yield data